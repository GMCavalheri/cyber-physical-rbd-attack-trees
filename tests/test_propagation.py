"""Phase 3: probability and attribute propagation.

Correctness conditions (plan, "Validation strategy"):
* all-physical models reduce exactly to classical RBD results;
* adding an OR alternative never decreases P(TOP); adding an AND requirement never increases it;
* exact propagation agrees with brute-force enumeration on any DAG.
"""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from strategies import models, probabilities, rbds

from cpsrbd.consequence_driven_analysis import navigation_case_study
from cpsrbd.probability_likelihood_propagation import (
    MIN_COST,
    MOST_LIKELY,
    POSSIBLE,
    PROBABILITY,
    bottom_up_probability,
    conditional_probability,
    enumerate_probability,
    evaluate,
    exact_probability,
    gate_probability,
    monte_carlo_probability,
    node_probabilities,
    origin_overrides,
    wilson_interval,
)
from cpsrbd.probability_likelihood_propagation import probability as prob_module
from cpsrbd.rbd import Block, KofN, Parallel, Series, bridge, bridge_reliability, reliability
from cpsrbd.rbd import to_unified as rbd_to_unified
from cpsrbd.unified_graph_model import (
    Gate,
    GateType,
    Origin,
    UnifiedModel,
    cyber_step,
    physical_event,
)

EXACT = 1e-12  # exact methods agree to rounding error

# ------------------------------------------------------------------ classical reductions


def test_series_parallel_kofn_reduce_to_closed_forms() -> None:
    R = [0.9, 0.8, 0.95]
    b = [Block(f"b{i}", r) for i, r in enumerate(R)]
    for rbd in (Series(tuple(b)), Parallel(tuple(b)), KofN(2, tuple(b))):
        m = rbd_to_unified(rbd)
        assert exact_probability(m) == pytest.approx(1 - reliability(rbd), abs=EXACT)
        assert bottom_up_probability(m) == pytest.approx(1 - reliability(rbd), abs=EXACT)


def test_bridge_exact_but_not_bottom_up() -> None:
    # The bridge converted to failure logic is AND over 4 path sets of OR of failures; every
    # component is in two path sets, so the model is a DAG and naive propagation is wrong.
    R = [0.9, 0.8, 0.95, 0.7, 0.85]
    m = rbd_to_unified(bridge(R))
    assert m.shared_events() == ["c1", "c2", "c3", "c4", "c5"]
    assert exact_probability(m) == pytest.approx(1 - bridge_reliability(R), abs=EXACT)
    assert abs(bottom_up_probability(m) - (1 - bridge_reliability(R))) > 1e-3


@settings(max_examples=60, deadline=None)
@given(rbds())
def test_all_physical_models_reduce_exactly_to_the_rbd(rbd) -> None:  # type: ignore[no-untyped-def]
    m = rbd_to_unified(rbd)
    assert exact_probability(m) == pytest.approx(1 - reliability(rbd), abs=EXACT)


# ------------------------------------------------------------------ exactness on DAGs


@settings(max_examples=80, deadline=None)
@given(models())
def test_exact_equals_enumeration_on_random_dags(m: UnifiedModel) -> None:
    assert exact_probability(m) == pytest.approx(enumerate_probability(m), abs=EXACT)


@settings(max_examples=60, deadline=None)
@given(models(tree=True))
def test_bottom_up_is_exact_on_trees(m: UnifiedModel) -> None:
    assert m.is_tree()
    assert bottom_up_probability(m) == pytest.approx(enumerate_probability(m), abs=EXACT)


def test_shared_event_textbook_example() -> None:
    # TOP = AND(OR(a, c), OR(b, c)): with c shared, P = P(c) + (1 - P(c)) P(a) P(b).
    m = UnifiedModel("top")
    m.add_events(physical_event(n, probability=p) for n, p in (("a", 0.3), ("b", 0.4), ("c", 0.2)))
    m.or_("x", "a", "c").or_("y", "b", "c").and_("top", "x", "y").validate()
    expected = 0.2 + 0.8 * 0.3 * 0.4
    assert exact_probability(m) == pytest.approx(expected, abs=EXACT)
    naive = (1 - 0.7 * 0.8) * (1 - 0.6 * 0.8)
    assert bottom_up_probability(m) == pytest.approx(naive, abs=EXACT)


def test_conditional_and_overrides() -> None:
    m = UnifiedModel("top")
    m.add_events(physical_event(n, probability=0.5) for n in "ab")
    m.and_("top", "a", "b").validate()
    assert conditional_probability(m, {"a": True}) == pytest.approx(0.5)
    assert conditional_probability(m, {"a": False}) == 0.0
    assert exact_probability(m, {"b": 1.0}) == pytest.approx(0.5)
    with pytest.raises(KeyError):
        exact_probability(m, {"nope": 1.0})


def test_gate_probability_formulas() -> None:
    assert gate_probability(GateType.AND, [0.5, 0.2]) == pytest.approx(0.1)
    assert gate_probability(GateType.OR, [0.5, 0.2]) == pytest.approx(0.6)
    assert gate_probability(GateType.KOFN, [0.5, 0.5, 0.5], 2) == pytest.approx(0.5)


def test_limits_on_exponential_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    m = rbd_to_unified(bridge([0.9] * 5))
    monkeypatch.setattr(prob_module, "MAX_SHARED", 3)
    monkeypatch.setattr(prob_module, "MAX_ENUMERATED", 3)
    with pytest.raises(ValueError, match="shared"):
        exact_probability(m)
    with pytest.raises(ValueError, match="enumerate"):
        enumerate_probability(m)


def test_zero_weight_branches_are_skipped() -> None:
    # c3 never fails (failure probability 0): the bridge becomes (1 || 2) in series with
    # (4 || 5), so P(fail) = 1 - (1 - 0.1^2)^2 with every component failing w.p. 0.1.
    m = rbd_to_unified(bridge([0.9] * 5))
    assert exact_probability(m, {"c3": 0.0}) == pytest.approx(1 - (1 - 0.1**2) ** 2, abs=EXACT)


# ------------------------------------------------------------------ monotonicity (coherence)


@settings(max_examples=60, deadline=None)
@given(models(), st.data())
def test_raising_any_leaf_never_lowers_the_top(m: UnifiedModel, data: st.DataObject) -> None:
    e = data.draw(st.sampled_from(m.basic_events()))
    higher = data.draw(st.floats(e.probability, 1.0))
    assert exact_probability(m, {e.name: higher}) >= exact_probability(m) - EXACT


def _with_extra_child(m: UnifiedModel, gate: str, p: float) -> UnifiedModel:
    g = m.gates[gate]
    m2 = m.copy()
    m2.add_event(physical_event("extra", probability=p))
    return m2.with_gate(Gate(g.name, g.kind, (*g.children, "extra"), g.k, g.description))


@settings(max_examples=60, deadline=None)
@given(models(), probabilities, st.data())
def test_adding_an_or_alternative_never_lowers_the_top(
    m: UnifiedModel, p: float, data: st.DataObject
) -> None:
    ors = [n for n, g in m.gates.items() if g.kind is GateType.OR]
    if not ors:
        return
    gate = data.draw(st.sampled_from(ors))
    assert exact_probability(_with_extra_child(m, gate, p)) >= exact_probability(m) - EXACT


@settings(max_examples=60, deadline=None)
@given(models(), probabilities, st.data())
def test_adding_an_and_requirement_never_raises_the_top(
    m: UnifiedModel, p: float, data: st.DataObject
) -> None:
    ands = [n for n, g in m.gates.items() if g.kind is GateType.AND]
    if not ands:
        return
    gate = data.draw(st.sampled_from(ands))
    assert exact_probability(_with_extra_child(m, gate, p)) <= exact_probability(m) + EXACT


# ------------------------------------------------------------------ Monte Carlo


def test_monte_carlo_interval_covers_the_exact_value() -> None:
    m = rbd_to_unified(bridge([0.6, 0.7, 0.5, 0.8, 0.65]))
    exact = exact_probability(m)
    r = monte_carlo_probability(m, samples=200_000, seed=1, batch=70_000)
    assert r.samples == 200_000
    assert r.low <= exact <= r.high
    assert r.estimate == r.hits / r.samples
    again = monte_carlo_probability(m, samples=200_000, seed=1, batch=70_000)
    assert again == r  # seeded and reproducible


def test_wilson_interval_textbook_value() -> None:
    # 95 % Wilson interval for 0 successes in 10 trials: [0, 0.2775] (Brown, Cai & DasGupta 2001)
    low, high = wilson_interval(0, 10)
    assert low == 0.0
    assert high == pytest.approx(0.27753, abs=1e-5)
    with pytest.raises(ValueError):
        wilson_interval(0, 0)


# ------------------------------------------------------------------ origins and the case study


def test_origin_views_of_the_case_study() -> None:
    m = navigation_case_study()
    full = exact_probability(m)
    physical = exact_probability(m, origin_overrides(m, Origin.PHYSICAL))
    cyber = exact_probability(m, origin_overrides(m, Origin.CYBER))
    assert full == pytest.approx(enumerate_probability(m), abs=EXACT)
    # Each partial view misses risk: the full model is above both, and above their union,
    # because mixed branches need one physical AND one cyber event.
    assert full > 1 - (1 - physical) * (1 - cyber)
    assert physical > 0 and cyber > 0


def test_node_probabilities_cover_every_node() -> None:
    m = navigation_case_study()
    probs = node_probabilities(m)
    assert set(probs) == set(m.reachable())
    assert probs["egi_1_hw"] == m.events["egi_1_hw"].probability


# ------------------------------------------------------------------ attribute domains


def attack_tree() -> UnifiedModel:
    # OR(AND(a, b), c): Lesson 1, exercise 5.
    m = UnifiedModel("top")
    m.add_events(
        [
            cyber_step("a", probability=0.5, cost=2),
            cyber_step("b", probability=0.4, cost=3),
            cyber_step("c", probability=0.1, cost=10),
        ]
    )
    m.and_("ab", "a", "b").or_("top", "ab", "c")
    return m.validate()


def test_attack_tree_domains() -> None:
    m = attack_tree()
    assert evaluate(m, PROBABILITY)["top"] == pytest.approx(0.28, abs=EXACT)
    assert evaluate(m, MIN_COST)["top"] == 5.0
    assert evaluate(m, MOST_LIKELY)["top"] == pytest.approx(0.2)
    assert evaluate(m, POSSIBLE)["top"] == 1.0


def test_kofn_in_every_domain() -> None:
    m = UnifiedModel("top")
    m.add_events(
        cyber_step(n, probability=p, cost=c)
        for n, p, c in [("a", 0.1, 5), ("b", 0.2, 1), ("c", 0.3, 3)]
    )
    m.kofn("top", 2, "a", "b", "c").validate()
    assert evaluate(m, MIN_COST)["top"] == 4.0
    assert evaluate(m, MOST_LIKELY)["top"] == pytest.approx(0.06)
    assert evaluate(m, PROBABILITY)["top"] == pytest.approx(exact_probability(m), abs=EXACT)
    assert evaluate(m, POSSIBLE)["top"] == 1.0


def test_physical_events_are_impossible_for_the_attacker() -> None:
    m = UnifiedModel("top")
    m.add_events([physical_event("p", probability=0.5), cyber_step("c", probability=0.5, cost=1)])
    m.and_("top", "p", "c").validate()
    assert evaluate(m, POSSIBLE)["top"] == 0.0
    assert math.isinf(evaluate(m, MIN_COST)["top"])


@settings(max_examples=60, deadline=None)
@given(models(tree=True, origins="cyber"))
def test_probability_domain_equals_exact_on_trees(m: UnifiedModel) -> None:
    assert evaluate(m, PROBABILITY)["top"] == pytest.approx(exact_probability(m), abs=EXACT)
