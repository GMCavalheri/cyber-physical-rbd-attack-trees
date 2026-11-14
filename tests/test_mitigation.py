"""Phase 5: mitigations as model transformations, assessments, portfolios and sensitivity."""

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from strategies import models

from cpsrbd.consequence_driven_analysis import navigation_case_study
from cpsrbd.critical_path_identification import min_attacker_cost, minimal_cut_sets
from cpsrbd.mitigation_tradeoff_analysis import (
    AddRedundancy,
    Category,
    EngineerOut,
    Mitigation,
    Portfolio,
    ReduceProbability,
    RequireStep,
    apply_all,
    assess,
    best_within_budget,
    case_study_mitigations,
    pareto_front,
    perturbed,
    portfolios,
    tornado,
    uncertainty_samples,
)
from cpsrbd.probability_likelihood_propagation import exact_probability
from cpsrbd.unified_graph_model import ModelError, Origin, UnifiedModel, cyber_step, physical_event

EXACT = 1e-12


def single(p: float = 0.1) -> UnifiedModel:
    m = UnifiedModel("top")
    m.add_events([physical_event("a", probability=p), cyber_step("c", probability=0.2, cost=3)])
    m.or_("top", "a", "c")
    return m.validate()


# ------------------------------------------------------------------ redundancy


def test_redundancy_without_common_cause_squares_the_probability() -> None:
    m = AddRedundancy("dup", 1.0, Category.PHYSICAL, events=("a",)).apply(single(0.1))
    assert m.is_gate("a") and "a/unit_a" in m.events
    # P(both units fail) = q^2 (independent units)
    assert exact_probability(m.rooted_at("a")) == pytest.approx(0.01, abs=EXACT)


def test_beta_factor_limits_redundancy() -> None:
    # Beta-factor model: Q = ((1 - beta) q)^2 + beta q - ((1 - beta) q)^2 * beta q
    q, beta = 0.1, 0.1
    m = AddRedundancy("dup", 1.0, Category.PHYSICAL, events=("a",), beta=beta).apply(single(q))
    ind, ccf = ((1 - beta) * q) ** 2, beta * q
    expected = 1 - (1 - ind) * (1 - ccf)
    assert exact_probability(m.rooted_at("a")) == pytest.approx(expected, abs=EXACT)
    full = AddRedundancy("dup", 1.0, Category.PHYSICAL, events=("a",), beta=1.0).apply(single(q))
    assert exact_probability(full.rooted_at("a")) == pytest.approx(q, abs=EXACT)


def test_redundancy_rejects_cyber_steps_and_bad_beta() -> None:
    with pytest.raises(ModelError):
        AddRedundancy("dup", 1.0, Category.PHYSICAL, events=("c",)).apply(single())
    with pytest.raises(ValueError):
        AddRedundancy("dup", 1.0, Category.PHYSICAL, events=("a",), beta=1.5).apply(single())
    with pytest.raises(ModelError):
        AddRedundancy("dup", 1.0, Category.PHYSICAL, events=("nope",)).apply(single())


@settings(max_examples=50, deadline=None)
@given(models(origins="physical"), st.floats(0.0, 1.0), st.data())
def test_redundancy_never_increases_risk(m: UnifiedModel, beta: float, data: st.DataObject) -> None:
    e = data.draw(st.sampled_from(m.basic_events())).name
    after = AddRedundancy("dup", 1.0, Category.PHYSICAL, events=(e,), beta=beta).apply(m)
    assert exact_probability(after) <= exact_probability(m) + EXACT


# ------------------------------------------------------------------ cyber controls


def test_reduce_probability_scales_and_adds_cost() -> None:
    m = ReduceProbability("harden", 1.0, Category.CYBER, event="c", factor=0.5, added_cost=2)
    out = m.apply(single())
    assert out.events["c"].probability == pytest.approx(0.1)
    assert out.events["c"].cost == 5.0
    with pytest.raises(ValueError):
        ReduceProbability("x", 1.0, Category.CYBER, event="c", factor=2.0).apply(single())


def test_require_step_inserts_an_and_gate() -> None:
    step = cyber_step("auth", probability=0.5, cost=7)
    m = RequireStep("auth", 1.0, Category.CYBER, target="c", step=step).apply(single())
    assert m.children("top") == ("a", "c+auth")
    assert m.children("c+auth") == ("c", "auth")
    assert min_attacker_cost(m) == 10.0
    assert exact_probability(m) == pytest.approx(1 - 0.9 * (1 - 0.1), abs=EXACT)
    # guarding the top event itself moves the top
    top = RequireStep("auth", 1.0, Category.CYBER, target="top", step=step).apply(single())
    assert top.top == "top+auth"
    with pytest.raises(ModelError):
        RequireStep("bad", 1.0, Category.CYBER, target="nope", step=step).apply(single())


@settings(max_examples=50, deadline=None)
@given(models(origins="cyber"), st.data())
def test_cyber_controls_never_lower_attacker_effort(m: UnifiedModel, data: st.DataObject) -> None:
    e = data.draw(st.sampled_from(m.basic_events())).name
    before_cost, before_q = min_attacker_cost(m), exact_probability(m)
    controls: list[Mitigation] = [
        ReduceProbability("r", 1.0, Category.CYBER, event=e, factor=0.5, added_cost=1.0),
        RequireStep(
            "s", 1.0, Category.CYBER, target=e, step=cyber_step("new", probability=0.5, cost=1)
        ),
        EngineerOut("o", 1.0, Category.ENGINEER_OUT, events=(e,)),
    ]
    for control in controls:
        after = control.apply(m)
        assert min_attacker_cost(after) >= before_cost
        assert exact_probability(after) <= before_q + EXACT


def test_engineer_out_removes_every_path_through_the_step() -> None:
    m = navigation_case_study()
    out = EngineerOut(
        "loader", 1.0, Category.ENGINEER_OUT, events=("compromise_maintenance_laptop",)
    ).apply(m)
    q = exact_probability(out)
    # equal to the probability of the cut sets that do not contain the laptop
    surviving = [c for c in minimal_cut_sets(m) if "compromise_maintenance_laptop" not in c]
    assert q == pytest.approx(exact_probability(m, {"compromise_maintenance_laptop": 0.0}))
    assert all(
        out.structure_function({e.name: e.name in c for e in out.basic_events()}) for c in surviving
    )
    assert min_attacker_cost(out) == 42.0


def test_base_mitigation_is_abstract() -> None:
    with pytest.raises(NotImplementedError):
        Mitigation("x", 1.0, Category.CYBER).apply(single())


# ------------------------------------------------------------------ assessments and portfolios


def test_assessment_properties() -> None:
    m = single()
    [a] = assess(m, [EngineerOut("o", 10.0, Category.ENGINEER_OUT, events=("c",))])
    assert a.q_before == pytest.approx(0.28) and a.q_after == pytest.approx(0.1)
    assert a.risk_reduction == pytest.approx(1 - 0.1 / 0.28)
    assert a.reduction_per_investment == pytest.approx(a.risk_reduction / 10)
    assert math.isinf(a.cost_after) and math.isinf(a.effort_gain)
    [free] = assess(m, [ReduceProbability("f", 0.0, Category.CYBER, event="c", added_cost=3)])
    assert math.isinf(free.reduction_per_investment)
    assert free.effort_gain == 2.0


def test_portfolios_enumerate_every_subset() -> None:
    m = single()
    options: list[Mitigation] = [
        AddRedundancy("dup", 5.0, Category.PHYSICAL, events=("a",)),
        EngineerOut("out", 10.0, Category.ENGINEER_OUT, events=("c",)),
    ]
    ps = portfolios(m, options)
    assert len(ps) == 4
    both = next(p for p in ps if len(p.names) == 2)
    assert both.investment == 15.0
    assert both.q == pytest.approx(0.01)
    assert both.physical_share == pytest.approx(1 / 3)
    assert both.q == pytest.approx(exact_probability(apply_all(m, options)))
    with pytest.raises(ValueError):
        portfolios(m, options * 7)


def test_pareto_front_and_budget() -> None:
    ps = [
        Portfolio(("a",), 10, 0.5, 5, 0),
        Portfolio(("b",), 10, 0.4, 3, 0),
        Portfolio(("c",), 20, 0.45, 9, 0),
        Portfolio((), 0, 0.9, 1, 0),
    ]
    assert [p.names for p in pareto_front(ps, "risk")] == [(), ("b",)]
    assert [p.names for p in pareto_front(ps, "effort")] == [(), ("a",), ("c",)]
    assert best_within_budget(ps, 15).names == ("b",)
    assert best_within_budget(ps, 15, "effort").names == ("a",)
    with pytest.raises(ValueError):
        pareto_front(ps, "beauty")


# ------------------------------------------------------------------ sensitivity


def test_tornado_bars() -> None:
    m = single()
    bars = tornado(m, factor=2.0)
    assert [b.event for b in bars] == ["c", "a"]  # c has the larger absolute swing
    c = bars[0]
    assert c.q_low == pytest.approx(1 - 0.9 * 0.9)
    assert c.q_high == pytest.approx(1 - 0.9 * 0.6)
    assert c.swing > 0
    with pytest.raises(ValueError):
        tornado(m, factor=0.5)


def test_perturbation_is_lognormal_around_the_nominal() -> None:
    m = single(0.01)
    rng = np.random.default_rng(3)
    draws = np.array([perturbed(m, rng).events["a"].probability for _ in range(4000)])
    # median = nominal, 95th percentile = nominal x EF (physical EF = 3)
    assert np.median(draws) == pytest.approx(0.01, rel=0.06)
    assert np.quantile(draws, 0.95) == pytest.approx(0.03, rel=0.08)
    with pytest.raises(ValueError):
        perturbed(m, rng, physical_error_factor=0.5)
    assert all(perturbed(m, rng).events[n].origin is m.events[n].origin for n in "ac")
    assert perturbed(m, rng).events["c"].origin is Origin.CYBER


def test_uncertainty_samples_use_common_draws() -> None:
    m = single()
    options: list[Mitigation] = [EngineerOut("out", 1.0, Category.ENGINEER_OUT, events=("c",))]
    s = uncertainty_samples(m, options, samples=50, seed=1)
    assert set(s) == {"baseline", "out"}
    assert s["out"].shape == (50,)
    assert np.all((s["out"] >= 0) & (s["out"] <= 1))
    again = uncertainty_samples(m, options, samples=50, seed=1)
    assert np.array_equal(again["out"], s["out"])


# ------------------------------------------------------------------ the case study


def test_case_study_catalogue() -> None:
    m = navigation_case_study()
    options = case_study_mitigations()
    assert len(options) == 8
    assert {o.category for o in options} == set(Category)
    by_name = {a.name: a for a in assess(m, options)}
    assert all(0.0 <= a.risk_reduction < 1.0 for a in by_name.values())
    # only engineering the laptop out moves the attacker's cheapest path far
    assert by_name["offline_software_loader"].cost_after == 42.0
    assert by_name["redundant_mission_computer"].cost_after == 5.0
    assert (
        by_name["redundant_mission_computer"].risk_reduction
        > by_name["offline_software_loader"].risk_reduction
    )
