"""Classical attack trees (Schneier 1999; Mauw and Oostdijk 2005), kept independent on purpose.

This module implements attack trees *as the security literature defines them* — a tree of AND
and OR nodes over attack steps, evaluated bottom-up — with its own evaluators that share no code
with the unified model. It exists so that the all-cyber reduction theorem
(``docs/formal-semantics.md``, Theorem 2) can be checked against an independent reference:
converting a tree with :func:`to_unified` and analysing it with the unified machinery must give
the classical answers.

* :func:`scenarios` — the propositional (set) semantics: the minimal sets of attack steps that
  achieve the root (Mauw and Oostdijk's attack suites, reduced to sets);
* :func:`probability` — success probability with independent steps (OR: 1 − ∏(1 − p),
  AND: ∏ p);
* :func:`min_cost` — the cheapest attack (OR: min, AND: sum).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cpsrbd.unified_graph_model import GateType, UnifiedModel, cyber_step


@dataclass(frozen=True)
class Step:
    """A leaf: an attack step with its success probability and cost."""

    name: str
    probability: float
    cost: float


@dataclass(frozen=True)
class And:
    name: str
    children: tuple[AttackTree, ...]


@dataclass(frozen=True)
class Or:
    name: str
    children: tuple[AttackTree, ...]


AttackTree = Step | And | Or


def scenarios(tree: AttackTree) -> set[frozenset[str]]:
    """Minimal attack scenarios: sets of steps that achieve the root, none containing another."""
    if isinstance(tree, Step):
        return {frozenset({tree.name})}
    kids = [scenarios(c) for c in tree.children]
    if isinstance(tree, Or):
        family = set().union(*kids)
    else:
        family = {frozenset()}
        for k in kids:
            family = {a | b for a in family for b in k}
    return {s for s in family if not any(o < s for o in family)}


def probability(tree: AttackTree) -> float:
    """Classical bottom-up success probability (independent steps; exact for trees)."""
    if isinstance(tree, Step):
        return tree.probability
    ps = [probability(c) for c in tree.children]
    if isinstance(tree, And):
        return math.prod(ps)
    return 1.0 - math.prod(1.0 - p for p in ps)


def min_cost(tree: AttackTree) -> float:
    """Classical bottom-up minimum attack cost."""
    if isinstance(tree, Step):
        return tree.cost
    costs = [min_cost(c) for c in tree.children]
    return math.fsum(costs) if isinstance(tree, And) else min(costs)


def to_unified(tree: AttackTree) -> UnifiedModel:
    """The same tree as a unified model: every step becomes a cyber basic event."""
    model = UnifiedModel(tree.name if not isinstance(tree, Step) else f"{tree.name}/goal")

    def add(node: AttackTree) -> str:
        if isinstance(node, Step):
            if node.name not in model.events:
                model.add_event(cyber_step(node.name, probability=node.probability, cost=node.cost))
            return node.name
        kids = [add(c) for c in node.children]
        kind = GateType.AND if isinstance(node, And) else GateType.OR
        model.add_gate(node.name, kind, kids)
        return node.name

    if isinstance(tree, Step):
        model.add_event(cyber_step(tree.name, probability=tree.probability, cost=tree.cost))
        model.or_(model.top, tree.name)
    else:
        add(tree)
    return model.validate()
