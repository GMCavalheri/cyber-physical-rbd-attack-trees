"""Classical RBD closed forms and the exactness of the RBD → unified-model duality.

Reference formulas: Rausand & Høyland, *System Reliability Theory: Models, Statistical Methods,
and Applications*, 2nd ed., Wiley, 2004, ch. 4 (series, parallel, k-out-of-n, bridge).
"""

import itertools
import math

import pytest
from hypothesis import given, settings
from strategies import rbds

from cpsrbd.rbd import (
    Block,
    KofN,
    Parallel,
    PathSets,
    Rbd,
    Series,
    at_least_k,
    block,
    block_names,
    bridge,
    bridge_reliability,
    k_out_of_n_identical,
    reliability,
    to_unified,
    works,
)
from cpsrbd.unified_graph_model import GateType, Origin

R = [0.9, 0.8, 0.95, 0.7, 0.85]


def enumerate_unreliability(rbd: Rbd) -> float:
    """Independent oracle: 1 - R by summing over every state of the blocks."""
    rel = {}
    for name in block_names(rbd):
        rel[name] = next(
            b.reliability for b in _iter_blocks(rbd) if b.name == name
        )  # first occurrence
    names = list(rel)
    failed = 0.0
    for states in itertools.product((False, True), repeat=len(names)):
        working = {n for n, s in zip(names, states, strict=True) if s}
        if not works(rbd, working):
            failed += math.prod(
                rel[n] if s else 1 - rel[n] for n, s in zip(names, states, strict=True)
            )
    return failed


def _iter_blocks(rbd: Rbd):  # type: ignore[no-untyped-def]
    if isinstance(rbd, Block):
        yield rbd
    elif isinstance(rbd, PathSets):
        yield from rbd.blocks
    else:
        for c in rbd.children:
            yield from _iter_blocks(c)


def test_series_and_parallel_closed_forms() -> None:
    blocks = tuple(Block(f"b{i}", r) for i, r in enumerate(R))
    assert reliability(Series(blocks)) == pytest.approx(math.prod(R), rel=1e-15)
    assert reliability(Parallel(blocks)) == pytest.approx(
        1 - math.prod(1 - r for r in R), rel=1e-15
    )


@pytest.mark.parametrize(("k", "n", "r"), [(1, 3, 0.9), (2, 3, 0.9), (3, 3, 0.9), (2, 4, 0.75)])
def test_k_out_of_n_matches_binomial_sum(k: int, n: int, r: float) -> None:
    rbd = KofN(k, tuple(Block(f"b{i}", r) for i in range(n)))
    assert reliability(rbd) == pytest.approx(k_out_of_n_identical(k, n, r), rel=1e-14)


def test_two_out_of_three_textbook_value() -> None:
    # 2oo3 with identical R: 3R^2 - 2R^3 (Rausand & Høyland, §4.5)
    r = 0.9
    assert k_out_of_n_identical(2, 3, r) == pytest.approx(3 * r**2 - 2 * r**3, rel=1e-15)


def test_k_out_of_n_edge_cases_reduce_to_series_and_parallel() -> None:
    blocks = tuple(Block(f"b{i}", r) for i, r in enumerate(R))
    assert reliability(KofN(len(R), blocks)) == pytest.approx(reliability(Series(blocks)))
    assert reliability(KofN(1, blocks)) == pytest.approx(reliability(Parallel(blocks)))


def test_at_least_k_poisson_binomial() -> None:
    p = [0.1, 0.5, 0.3]
    exact = sum(
        math.prod(pi if s else 1 - pi for pi, s in zip(p, states, strict=True))
        for states in itertools.product((False, True), repeat=3)
        if sum(states) >= 2
    )
    assert at_least_k(p, 2) == pytest.approx(exact, rel=1e-15)
    assert at_least_k(p, 0) == pytest.approx(1.0)


def test_bridge_identical_components_polynomial() -> None:
    # R_bridge = 2R^2 + 2R^3 - 5R^4 + 2R^5 for identical components (Rausand & Høyland, §4.6)
    for r in (0.5, 0.9, 0.99):
        expected = 2 * r**2 + 2 * r**3 - 5 * r**4 + 2 * r**5
        assert bridge_reliability([r] * 5) == pytest.approx(expected, rel=1e-14)
        assert reliability(bridge([r] * 5)) == pytest.approx(expected, rel=1e-14)


def test_bridge_distinct_components_pivot_equals_enumeration() -> None:
    assert reliability(bridge(R)) == pytest.approx(bridge_reliability(R), rel=1e-14)


def test_block_from_failure_rate() -> None:
    b = block("pump", failure_rate=1e-4, exposure_time=100.0)
    assert b.reliability == pytest.approx(math.exp(-0.01), rel=1e-15)
    with pytest.raises(ValueError):
        block("pump")
    with pytest.raises(ValueError):
        Block("x", 1.5)


def test_invalid_structures() -> None:
    with pytest.raises(ValueError):
        KofN(0, (Block("a", 0.9),))
    with pytest.raises(ValueError):
        PathSets((Block("a", 0.9),), (frozenset({"b"}),))
    with pytest.raises(ValueError):
        PathSets((Block("a", 0.9), Block("a", 0.8)), (frozenset({"a"}),))
    with pytest.raises(ValueError):
        bridge([0.9] * 4)


def test_repeated_block_is_rejected_by_closed_forms() -> None:
    a = Block("a", 0.9)
    with pytest.raises(ValueError, match="more than once"):
        reliability(Parallel((Series((a, Block("b", 0.8))), Series((a, Block("c", 0.7))))))


# ---------------------------------------------------------------- duality (exact conversion)


def assert_dual(rbd: Rbd) -> None:
    """For every state of the blocks, the unified top event happens iff the RBD fails."""
    model = to_unified(rbd)
    names = block_names(rbd)
    assert {e.name for e in model.basic_events()} == set(names)
    assert model.origins() == {Origin.PHYSICAL}
    for states in itertools.product((False, True), repeat=len(names)):
        working = {n for n, s in zip(names, states, strict=True) if s}
        failed = {n: n not in working for n in names}
        assert model.structure_function(failed) is (not works(rbd, working))


def test_duality_series_parallel_kofn() -> None:
    b = [Block(f"b{i}", r) for i, r in enumerate(R)]
    rbd = Series((b[0], Parallel((b[1], b[2]), name="redundant"), KofN(2, (b[3], b[4], b[2]))))
    with pytest.raises(ValueError):
        reliability(rbd)  # b2 repeats
    assert_dual(rbd)
    m = to_unified(Series((b[0], Parallel((b[1], b[2]), name="redundant"))))
    assert m.gates["system_failure"].kind is GateType.OR
    assert m.gates["redundant"].kind is GateType.AND


def test_duality_kofn_threshold_flips() -> None:
    # 2-out-of-3 good ⇔ 2-out-of-3 failed is the system failure (n - k + 1 = 2)
    m = to_unified(KofN(2, tuple(Block(f"b{i}", 0.9) for i in range(3))))
    assert m.gates["system_failure"].k == 2
    m = to_unified(KofN(1, tuple(Block(f"b{i}", 0.9) for i in range(4))))
    assert m.gates["system_failure"].k == 4


def test_duality_bridge_and_single_block() -> None:
    assert_dual(bridge(R))
    assert_dual(Series((Block("x", 0.9), bridge(R, name="br"))))
    assert_dual(Block("only", 0.9))


def test_probabilities_are_complements() -> None:
    m = to_unified(Series((Block("a", 0.9), Block("b", 0.8))))
    assert m.events["a"].probability == pytest.approx(0.1)
    assert m.events["b"].probability == pytest.approx(0.2)


def test_inconsistent_repeated_block_is_rejected() -> None:
    with pytest.raises(ValueError, match="two different"):
        to_unified(Parallel((Block("a", 0.9), Series((Block("a", 0.8), Block("b", 0.9))))))


# ---------------------------------------------------------------- random series-parallel RBDs


@settings(max_examples=60, deadline=None)
@given(rbds())
def test_random_rbds_closed_form_equals_enumeration_and_dual_is_exact(rbd: Rbd) -> None:
    assert 1 - reliability(rbd) == pytest.approx(enumerate_unreliability(rbd), abs=1e-12)
    assert_dual(rbd)
