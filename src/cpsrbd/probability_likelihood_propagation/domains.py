"""Attribute domains: one bottom-up evaluator for many attack-tree and fault-tree attributes.

Mauw and Oostdijk (2005) showed that the quantitative questions asked of attack trees share
one pattern: give each leaf a value, and combine children with one operator for OR and one for
AND. If the pair of operators has the right algebraic properties (a semiring), the bottom-up
result does not depend on how the tree is written, as long as it is a tree.

=================  ==================  ===============  ======================
domain             leaf value          OR               AND
=================  ==================  ===============  ======================
probability        p (independent)     1 - prod(1 - p)  prod(p)
min attacker cost  cost (inf: cannot)  min              sum
most likely path   p                   max              prod(p)
possible           cost < inf          any              all
=================  ==================  ===============  ======================

A k-out-of-n gate is the OR, over every k-subset of its children, of the AND of that subset;
for the min/max domains that reduces to combining the k best children.

On a DAG, AND gates whose children share a basic event count that event twice (cost paid
twice, probability multiplied twice), so the bottom-up value is pessimistic for the attacker.
The exact values come from minimal cut sets (:mod:`cpsrbd.critical_path_identification`).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from cpsrbd.rbd import at_least_k
from cpsrbd.unified_graph_model import BasicEvent, GateType, UnifiedModel


@dataclass(frozen=True)
class Domain:
    """A leaf valuation plus the OR / AND / k-of-n combinators."""

    name: str
    leaf: Callable[[BasicEvent], float]
    or_: Callable[[Sequence[float]], float]
    and_: Callable[[Sequence[float]], float]
    kofn: Callable[[Sequence[float], int], float]


def _sum_k_smallest(values: Sequence[float], k: int) -> float:
    return math.fsum(sorted(values)[:k])


def _prod_k_largest(values: Sequence[float], k: int) -> float:
    return math.prod(sorted(values, reverse=True)[:k])


PROBABILITY = Domain(
    "probability",
    leaf=lambda e: e.probability,
    or_=lambda v: 1.0 - math.prod(1.0 - x for x in v),
    and_=math.prod,
    kofn=lambda v, k: at_least_k(list(v), k),
)

MIN_COST = Domain(
    "min attacker cost",
    leaf=lambda e: e.cost,
    or_=min,
    and_=math.fsum,
    kofn=_sum_k_smallest,
)

MOST_LIKELY = Domain(
    "most likely scenario",
    leaf=lambda e: e.probability,
    or_=max,
    and_=math.prod,
    kofn=_prod_k_largest,
)

POSSIBLE = Domain(
    "possible for the attacker",
    leaf=lambda e: 0.0 if math.isinf(e.cost) else 1.0,
    or_=lambda v: float(any(x > 0 for x in v)),
    and_=lambda v: float(all(x > 0 for x in v)),
    kofn=lambda v, k: float(sum(x > 0 for x in v) >= k),
)


def evaluate(model: UnifiedModel, domain: Domain) -> dict[str, float]:
    """Bottom-up value of every reachable node in the given domain (tree semantics)."""
    model.validate()
    values: dict[str, float] = {}
    for name in model.bottom_up():
        if name in model.events:
            values[name] = domain.leaf(model.events[name])
            continue
        gate = model.gates[name]
        child_values = [values[c] for c in gate.children]
        if gate.kind is GateType.AND:
            values[name] = domain.and_(child_values)
        elif gate.kind is GateType.OR:
            values[name] = domain.or_(child_values)
        else:
            assert gate.k is not None
            values[name] = domain.kofn(child_values, gate.k)
    return values
