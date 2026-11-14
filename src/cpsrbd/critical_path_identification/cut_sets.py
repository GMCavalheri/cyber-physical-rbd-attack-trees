r"""Minimal cut sets and the lowest-effort paths to the consequence.

A **cut set** is a set of basic events whose joint occurrence makes the top event happen; it is
**minimal** if no proper subset does. For a coherent model, the top event is exactly the OR of
the ANDs of its minimal cut sets:

.. math::

    \text{TOP} = \bigvee_{C \in \mathcal{C}} \bigwedge_{e \in C} e.

In fault-tree language each minimal cut set is a minimal failure scenario; in attack-tree
language (Mauw and Oostdijk's semantics) it is a minimal **attack scenario**. In the unified
model a cut set can be physical-only, cyber-only or mixed, and that is the vocabulary used for
"paths" to the consequence.

The cut sets are computed by Boolean expansion from the leaves up (OR: union of the children's
families; AND: pairwise unions; k-of-n: OR over every k-subset of children), removing
non-minimal sets at each node. This gives the same family as the classical top-down MOCUS
algorithm (Fussell and Vesely, 1972), and memoisation makes shared sub-graphs cheap.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from cpsrbd.unified_graph_model import GateType, Origin, UnifiedModel

Family = list[frozenset[str]]
MAX_CUT_SETS = 100_000


def _minimize(family: Iterable[frozenset[str]]) -> Family:
    """Remove duplicates and every set that contains another set of the family."""
    unique = sorted(set(family), key=lambda s: (len(s), sorted(s)))
    kept: Family = []
    for candidate in unique:
        if not any(k <= candidate for k in kept):
            kept.append(candidate)
    return kept


def _and(families: list[Family]) -> Family:
    result: Family = [frozenset()]
    for family in families:
        result = _minimize(a | b for a in result for b in family)
        if len(result) > MAX_CUT_SETS:
            raise ValueError(f"more than {MAX_CUT_SETS} cut sets; the model is too large")
    return result


def minimal_cut_sets(model: UnifiedModel) -> Family:
    """All minimal cut sets of the top event, smallest first."""
    model.validate()
    memo: dict[str, Family] = {}
    for name in model.bottom_up():
        if name in model.events:
            memo[name] = [frozenset({name})]
            continue
        gate = model.gates[name]
        kids = [memo[c] for c in gate.children]
        if gate.kind is GateType.OR:
            memo[name] = _minimize(itertools.chain.from_iterable(kids))
        elif gate.kind is GateType.AND:
            memo[name] = _and(kids)
        else:
            assert gate.k is not None
            subsets = itertools.combinations(kids, gate.k)
            memo[name] = _minimize(itertools.chain.from_iterable(_and(list(s)) for s in subsets))
    return memo[model.top]


class PathKind(StrEnum):
    PHYSICAL = "physical"
    CYBER = "cyber"
    MIXED = "mixed"


@dataclass(frozen=True)
class CutSet:
    """A minimal cut set with the attributes used to rank it.

    ``probability`` is the product of the event probabilities (the probability that this
    scenario's events all happen). ``attacker_cost`` sums the cyber steps' costs (physical
    events cost the attacker nothing to *wait for*, but cannot be bought).
    ``physical_probability`` is the product over the physical events only: for a mixed set it
    is the chance that the failures the attacker needs are present.
    """

    events: frozenset[str]
    probability: float
    attacker_cost: float
    physical_probability: float
    n_physical: int
    n_cyber: int

    @property
    def kind(self) -> PathKind:
        if self.n_cyber == 0:
            return PathKind.PHYSICAL
        if self.n_physical == 0:
            return PathKind.CYBER
        return PathKind.MIXED

    @property
    def attacker_controlled(self) -> bool:
        """True when the attacker alone can complete the scenario (no physical failure needed)."""
        return self.n_physical == 0

    @property
    def effort(self) -> float:
        r"""Unified effort :math:`-\ln P`: lower is easier (adds along AND, like cost)."""
        return math.inf if self.probability == 0.0 else -math.log(self.probability)

    def label(self) -> str:
        return " + ".join(sorted(self.events))


def describe(model: UnifiedModel, cut_sets: Iterable[frozenset[str]] | None = None) -> list[CutSet]:
    """Attach probability, cost and composition to each cut set (all of them by default)."""
    if cut_sets is None:
        cut_sets = minimal_cut_sets(model)
    described = []
    for cs in cut_sets:
        events = [model.events[n] for n in cs]
        physical = [e for e in events if e.origin is Origin.PHYSICAL]
        cyber = [e for e in events if e.origin is Origin.CYBER]
        described.append(
            CutSet(
                events=frozenset(cs),
                probability=math.prod(e.probability for e in events),
                attacker_cost=math.fsum(e.cost for e in cyber),
                physical_probability=math.prod(e.probability for e in physical),
                n_physical=len(physical),
                n_cyber=len(cyber),
            )
        )
    return described


def most_likely(model: UnifiedModel, n: int | None = None) -> list[CutSet]:
    """Cut sets by decreasing probability: the lowest-effort paths in the unified metric."""
    ranked = sorted(describe(model), key=lambda c: (-c.probability, c.label()))
    return ranked if n is None else ranked[:n]


def cheapest_attacks(model: UnifiedModel, n: int | None = None) -> list[CutSet]:
    """Attacker-controlled (cyber-only) cut sets by increasing attacker cost."""
    ranked = sorted(
        (c for c in describe(model) if c.attacker_controlled),
        key=lambda c: (c.attacker_cost, -c.probability, c.label()),
    )
    return ranked if n is None else ranked[:n]


def min_attacker_cost(model: UnifiedModel) -> float:
    """Exact minimum attacker cost to the top event (∞ if no purely cyber path exists).

    This is the min-cost attribute evaluated over minimal cut sets, so on a DAG it pays for a
    shared step once, unlike the bottom-up domain evaluation.
    """
    attacks = cheapest_attacks(model, 1)
    return attacks[0].attacker_cost if attacks else math.inf


def opportunistic_front(model: UnifiedModel) -> list[CutSet]:
    """Pareto front of all cut sets on (attacker cost ↓, physical-precondition probability ↑).

    A physical-only scenario costs the attacker nothing but depends entirely on chance; a
    cyber-only one is certain to be available but costs effort; a mixed one trades the two
    (the attacker acts when, or betting that, a failure is present). The front keeps every
    scenario that no other beats on both counts.
    """
    cut_sets = describe(model)
    front = [
        c
        for c in cut_sets
        if not any(
            o.attacker_cost <= c.attacker_cost
            and o.physical_probability >= c.physical_probability
            and (
                o.attacker_cost < c.attacker_cost or o.physical_probability > c.physical_probability
            )
            for o in cut_sets
        )
    ]
    return sorted(front, key=lambda c: (c.attacker_cost, -c.physical_probability, c.label()))


def activated(model: UnifiedModel, events: Iterable[str]) -> set[str]:
    """Every node (gates and events) that happens when exactly ``events`` happen.

    Used to draw a scenario: the events plus the chain of gates they trigger up to the top.
    """
    happened = set(events)
    values: dict[str, bool] = {}
    for name in model.bottom_up():
        if name in model.events:
            values[name] = name in happened
        else:
            gate = model.gates[name]
            values[name] = sum(values[c] for c in gate.children) >= gate.threshold()
    return {n for n, v in values.items() if v}
