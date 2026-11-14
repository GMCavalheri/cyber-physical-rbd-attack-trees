"""The theorems of docs/formal-semantics.md, checked on random models.

Theorem 1 (all-physical → classical RBD) is in test_propagation.py; Theorem 3 (Shannon
exactness) and Proposition 4 (monotonicity) are there too. This file covers Theorem 2
(all-cyber → classical attack tree, against the independent implementation in
cpsrbd.attack_tree) and Proposition 5 (the interaction gap is a probability).
"""

import itertools
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from strategies import models

from cpsrbd import attack_tree as at
from cpsrbd.consequence_driven_analysis import navigation_case_study
from cpsrbd.critical_path_identification import PathKind, describe, min_attacker_cost
from cpsrbd.critical_path_identification import minimal_cut_sets as mcs
from cpsrbd.probability_likelihood_propagation import (
    MIN_COST,
    PROBABILITY,
    bottom_up_probability,
    evaluate,
    exact_probability,
    origin_decomposition,
)
from cpsrbd.unified_graph_model import Origin, UnifiedModel

EXACT = 1e-12


@st.composite
def attack_trees(draw: st.DrawFn, depth: int = 3, share: bool = False) -> at.AttackTree:
    """Random attack trees; with ``share=True`` a step name may be reused (a DAG in disguise)."""
    steps: list[at.Step] = []
    gates = [0]

    def leaf() -> at.Step:
        if share and steps and draw(st.booleans()):
            return draw(st.sampled_from(steps))
        s = at.Step(f"s{len(steps)}", draw(st.floats(0.01, 0.99)), draw(st.integers(1, 20)))
        steps.append(s)
        return s

    def build(d: int) -> at.AttackTree:
        if d == 0 or draw(st.integers(0, 2)) == 0:
            return leaf()
        gates[0] += 1
        name = f"g{gates[0]}"
        kids: list[at.AttackTree] = []
        for _ in range(draw(st.integers(1, 3))):
            kid = build(d - 1)
            if kid not in kids:
                kids.append(kid)
        cls = at.And if draw(st.booleans()) else at.Or
        return cls(name, tuple(kids))

    root = build(depth)
    if isinstance(root, at.Step):
        return at.Or("root", (root,))
    return root


def test_classical_evaluators_on_a_textbook_tree() -> None:
    # OR(AND(a, b), c): Lesson 1, exercise 5
    tree = at.Or(
        "goal",
        (at.And("ab", (at.Step("a", 0.5, 2), at.Step("b", 0.4, 3))), at.Step("c", 0.1, 10)),
    )
    assert at.scenarios(tree) == {frozenset("ab"), frozenset("c")}
    assert at.probability(tree) == pytest.approx(0.28)
    assert at.min_cost(tree) == 5.0
    m = at.to_unified(tree)
    assert m.top == "goal" and m.origins() == {Origin.CYBER}


def test_single_step_tree_converts() -> None:
    m = at.to_unified(at.Step("only", 0.3, 4))
    assert exact_probability(m) == pytest.approx(0.3)
    assert min_attacker_cost(m) == 4.0


@settings(max_examples=100, deadline=None)
@given(attack_trees())
def test_theorem_2_all_cyber_trees_reduce_to_classical_attack_trees(tree: at.AttackTree) -> None:
    m = at.to_unified(tree)
    # (a) Boolean semantics: minimal cut sets = minimal attack scenarios
    assert set(mcs(m)) == at.scenarios(tree)
    # (b) probability domain: exact unified = bottom-up unified = classical
    assert exact_probability(m) == pytest.approx(at.probability(tree), abs=EXACT)
    assert evaluate(m, PROBABILITY)[m.top] == pytest.approx(at.probability(tree), abs=EXACT)
    # (c) min-cost domain: exact over cut sets = bottom-up = classical
    assert min_attacker_cost(m) == pytest.approx(at.min_cost(tree))
    assert evaluate(m, MIN_COST)[m.top] == pytest.approx(at.min_cost(tree))


@settings(max_examples=100, deadline=None)
@given(attack_trees(share=True))
def test_shared_steps_semantics_still_agree_but_bottom_up_numbers_do_not(
    tree: at.AttackTree,
) -> None:
    m = at.to_unified(tree)
    # the set semantics is name-based, so sharing is handled correctly by both ...
    assert set(mcs(m)) == at.scenarios(tree)
    # ... and the exact methods are bounded by the classical bottom-up numbers where they must be
    assert min_attacker_cost(m) <= at.min_cost(tree) + 1e-9
    assert bottom_up_probability(m) == pytest.approx(at.probability(tree), abs=EXACT)


# ------------------------------------------------------------------ Proposition 5


def gap_by_enumeration(m: UnifiedModel) -> float:
    """P(TOP happens but no physical-only and no cyber-only cut set has happened)."""
    cut_sets = describe(m)
    pure = [c.events for c in cut_sets if c.kind is not PathKind.MIXED]
    events = m.basic_events()
    total = 0.0
    for states in itertools.product((False, True), repeat=len(events)):
        up = {e.name for e, s in zip(events, states, strict=True) if s}
        failed = {e.name: e.name in up for e in events}
        if m.structure_function(failed) and not any(c <= up for c in pure):
            total += math.prod(
                e.probability if s else 1 - e.probability
                for e, s in zip(events, states, strict=True)
            )
    return total


@settings(max_examples=80, deadline=None)
@given(models())
def test_proposition_5_interaction_gap(m: UnifiedModel) -> None:
    d = origin_decomposition(m)
    assert d.gap >= -EXACT
    assert d.gap == pytest.approx(gap_by_enumeration(m), abs=1e-12)
    has_mixed = any(c.kind is PathKind.MIXED and c.probability > 0 for c in describe(m))
    if not has_mixed:
        assert d.gap == pytest.approx(0.0, abs=EXACT)


def test_case_study_gap_is_the_mixed_branch() -> None:
    d = origin_decomposition(navigation_case_study())
    assert d.gap_share == pytest.approx(0.3113, abs=5e-4)
    assert d.full == pytest.approx(d.separate + d.gap)


def test_gap_share_of_an_impossible_top_event_is_zero() -> None:
    m = at.to_unified(at.Step("only", 0.0, 4))
    assert origin_decomposition(m).gap_share == 0.0
