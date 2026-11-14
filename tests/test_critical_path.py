"""Phase 4: minimal cut sets, lowest-effort paths and importance measures.

Reference values: Rausand & Høyland, *System Reliability Theory*, 2nd ed., 2004 (bridge cut sets,
§4.6; importance measures, §5.7-5.9); Mauw & Oostdijk 2005 (attack scenarios = minimal sets).
"""

import itertools
import math

import pytest
from hypothesis import given, settings
from strategies import models

from cpsrbd.consequence_driven_analysis import navigation_case_study
from cpsrbd.critical_path_identification import (
    PathKind,
    activated,
    cheapest_attacks,
    describe,
    importance_measures,
    min_attacker_cost,
    minimal_cut_sets,
    most_likely,
    opportunistic_front,
)
from cpsrbd.critical_path_identification import cut_sets as cut_sets_module
from cpsrbd.probability_likelihood_propagation import (
    MIN_COST,
    MOST_LIKELY,
    evaluate,
    exact_probability,
)
from cpsrbd.rbd import Block, KofN, bridge, to_unified
from cpsrbd.unified_graph_model import UnifiedModel, cyber_step, physical_event


def fs(*sets: str) -> set[frozenset[str]]:
    return {frozenset(s.split()) for s in sets}


def test_bridge_cut_sets() -> None:
    m = to_unified(bridge([0.9] * 5))
    assert set(minimal_cut_sets(m)) == fs("c1 c2", "c4 c5", "c1 c3 c5", "c2 c3 c4")


def test_two_out_of_three_cut_sets() -> None:
    m = to_unified(KofN(2, tuple(Block(n, 0.9) for n in "abc")))
    assert set(minimal_cut_sets(m)) == fs("a b", "a c", "b c")


def test_shared_event_absorbs_larger_sets() -> None:
    # (a or c) and (b or c) = c or (a and b)
    m = UnifiedModel("top")
    m.add_events(physical_event(n, probability=0.1) for n in "abc")
    m.or_("x", "a", "c").or_("y", "b", "c").and_("top", "x", "y").validate()
    cs = minimal_cut_sets(m)
    assert cs == [frozenset("c"), frozenset("ab")]  # smallest first


def test_cut_set_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cut_sets_module, "MAX_CUT_SETS", 2)
    with pytest.raises(ValueError, match="too large"):
        minimal_cut_sets(to_unified(bridge([0.9] * 5)))


@settings(max_examples=80, deadline=None)
@given(models())
def test_cut_sets_represent_the_structure_function_exactly(m: UnifiedModel) -> None:
    cs = minimal_cut_sets(m)
    names = [e.name for e in m.basic_events()]
    for states in itertools.product((False, True), repeat=len(names)):
        failed = dict(zip(names, states, strict=True))
        up = {n for n, s in failed.items() if s}
        assert m.structure_function(failed) is any(c <= up for c in cs)
    # minimality: dropping any event breaks every cut set
    for c in cs:
        for e in c:
            rest = {n: n in c and n != e for n in names}
            assert not m.structure_function(rest)


@settings(max_examples=60, deadline=None)
@given(models(origins="cyber"))
def test_min_cost_over_cut_sets_bounds_the_bottom_up_value(m: UnifiedModel) -> None:
    exact = min_attacker_cost(m)
    bottom_up = evaluate(m, MIN_COST)[m.top]
    assert exact <= bottom_up + 1e-9  # bottom-up may pay twice for a shared step
    if m.is_tree():
        assert exact == pytest.approx(bottom_up)


@settings(max_examples=60, deadline=None)
@given(models(tree=True))
def test_most_likely_domain_equals_best_cut_set_on_trees(m: UnifiedModel) -> None:
    best = most_likely(m, 1)[0]
    assert evaluate(m, MOST_LIKELY)[m.top] == pytest.approx(best.probability, rel=1e-12)


def test_shared_step_is_paid_once() -> None:
    # Two goals that both need the same foothold, combined by AND.
    m = UnifiedModel("top")
    m.add_events(
        [
            cyber_step("foothold", probability=0.5, cost=10),
            cyber_step("x", probability=0.5, cost=1),
            cyber_step("y", probability=0.5, cost=1),
        ]
    )
    m.and_("gx", "foothold", "x").and_("gy", "foothold", "y").and_("top", "gx", "gy").validate()
    assert evaluate(m, MIN_COST)["top"] == 22.0  # bottom-up pays for the foothold twice
    assert min_attacker_cost(m) == 12.0


def test_describe_and_kinds() -> None:
    m = UnifiedModel("top")
    m.add_events(
        [
            physical_event("p", probability=0.2),
            cyber_step("c", probability=0.1, cost=3),
            cyber_step("d", probability=0.3, cost=1),
        ]
    )
    m.and_("mixed", "p", "c").or_("top", "mixed", "d").validate()
    by_label = {c.label(): c for c in describe(m)}
    mixed, cyber = by_label["c + p"], by_label["d"]
    assert mixed.kind is PathKind.MIXED and not mixed.attacker_controlled
    assert mixed.probability == pytest.approx(0.02)
    assert mixed.attacker_cost == 3.0 and mixed.physical_probability == pytest.approx(0.2)
    assert mixed.effort == pytest.approx(-math.log(0.02))
    assert cyber.kind is PathKind.CYBER and cyber.physical_probability == 1.0
    assert [c.label() for c in most_likely(m)] == ["d", "c + p"]
    assert [c.label() for c in cheapest_attacks(m)] == ["d"]
    zero = describe(m.with_event(cyber_step("d", probability=0.0, cost=1)), [frozenset("d")])
    assert math.isinf(zero[0].effort)


def test_no_attack_path_means_infinite_cost() -> None:
    m = to_unified(bridge([0.9] * 5))
    assert min_attacker_cost(m) == math.inf
    assert all(c.kind is PathKind.PHYSICAL for c in describe(m))


def test_activated_traces_the_scenario_to_the_top() -> None:
    m = navigation_case_study()
    for c in minimal_cut_sets(m):
        nodes = activated(m, c)
        assert m.top in nodes and c <= nodes
    assert activated(m, []) == set()


# ------------------------------------------------------------------ importance measures


def test_importance_series_system() -> None:
    # OR(a, b): Q = 1 - (1 - qa)(1 - qb); I_B(a) = 1 - qb; FV(a) = qa / Q; RRW(a) = Q / qb
    m = UnifiedModel("top")
    m.add_events([physical_event("a", probability=0.1), physical_event("b", probability=0.2)])
    m.or_("top", "a", "b").validate()
    q = 0.28
    rows = {r.event: r for r in importance_measures(m)}
    a = rows["a"]
    assert a.birnbaum == pytest.approx(0.8)
    assert a.criticality == pytest.approx(0.8 * 0.1 / q)
    assert a.fussell_vesely == pytest.approx(0.1 / q)
    assert a.raw == pytest.approx(1 / q)
    assert a.rrw == pytest.approx(q / 0.2)
    assert a.q_without == pytest.approx(0.2)


def test_importance_parallel_system() -> None:
    # AND(a, b): Q = qa qb; I_B(a) = qb; FV(a) = 1; RAW(a) = 1/qa; RRW(a) = ∞
    m = UnifiedModel("top")
    m.add_events([physical_event("a", probability=0.1), physical_event("b", probability=0.2)])
    m.and_("top", "a", "b").validate()
    a = {r.event: r for r in importance_measures(m)}["a"]
    assert a.birnbaum == pytest.approx(0.2)
    assert a.fussell_vesely == pytest.approx(1.0)
    assert a.raw == pytest.approx(10.0)
    assert math.isinf(a.rrw)


def test_birnbaum_is_the_derivative() -> None:
    m = navigation_case_study()
    h = 1e-6
    for r in importance_measures(m)[:5]:
        q = r.probability
        lo = exact_probability(m, {r.event: q - h})
        hi = exact_probability(m, {r.event: q + h})
        assert (hi - lo) / (2 * h) == pytest.approx(r.birnbaum, rel=1e-6)


def test_importance_needs_a_possible_top_event() -> None:
    m = UnifiedModel("top")
    m.add_event(physical_event("a", probability=0.0))
    m.or_("top", "a").validate()
    with pytest.raises(ValueError):
        importance_measures(m)


# ------------------------------------------------------------------ the case study


def test_case_study_paths() -> None:
    m = navigation_case_study()
    assert len(minimal_cut_sets(m)) == 12
    top = most_likely(m, 3)
    assert [c.label() for c in top] == [
        "mc_hw",
        "gnss_spoof + integrity_monitor_miss",
        "compromise_maintenance_laptop + flood_bus",
    ]
    assert [c.kind for c in top] == [PathKind.PHYSICAL, PathKind.MIXED, PathKind.CYBER]
    assert min_attacker_cost(m) == 5.0
    front = opportunistic_front(m)
    assert [c.label() for c in front] == [
        "mc_hw",
        "gnss_spoof + integrity_monitor_miss",
        "compromise_maintenance_laptop + flood_bus",
    ]


def test_case_study_importance_ranks_the_spof_and_the_mixed_path() -> None:
    m = navigation_case_study()
    rows = importance_measures(m)
    assert rows[0].event == "mc_hw"
    assert {rows[1].event, rows[2].event} == {"gnss_spoof", "integrity_monitor_miss"}
    laptop = next(r for r in rows if r.event == "compromise_maintenance_laptop")
    assert laptop.q_without == pytest.approx(exact_probability(m, {laptop.event: 0.0}))
