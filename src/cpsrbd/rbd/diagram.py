"""Series/parallel/k-out-of-n and path-set RBDs, closed-form reliability, exact dual conversion."""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from cpsrbd.unified_graph_model import (
    GateType,
    UnifiedModel,
    physical_event,
    probability_from_rate,
)


@dataclass(frozen=True)
class Block:
    """One component with reliability ``reliability`` (probability it works over the window)."""

    name: str
    reliability: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.reliability <= 1.0:
            raise ValueError(f"{self.name}: reliability {self.reliability} is not in [0, 1]")


@dataclass(frozen=True)
class Series:
    children: tuple[Rbd, ...]
    name: str = ""


@dataclass(frozen=True)
class Parallel:
    children: tuple[Rbd, ...]
    name: str = ""


@dataclass(frozen=True)
class KofN:
    """Works if at least ``k`` of the children work."""

    k: int
    children: tuple[Rbd, ...]
    name: str = ""

    def __post_init__(self) -> None:
        if not 1 <= self.k <= len(self.children):
            raise ValueError(f"k = {self.k} must be in 1..{len(self.children)}")


@dataclass(frozen=True)
class PathSets:
    """A general (not series-parallel) structure given by its minimal path sets.

    The system works when every block of at least one path set works. Blocks are referenced
    by name and listed once in ``blocks``.
    """

    blocks: tuple[Block, ...]
    path_sets: tuple[frozenset[str], ...]
    name: str = ""

    def __post_init__(self) -> None:
        names = {b.name for b in self.blocks}
        if len(names) != len(self.blocks):
            raise ValueError("block names must be unique")
        for path in self.path_sets:
            if not path or not path <= names:
                raise ValueError(f"path set {sorted(path)} refers to unknown blocks")


Rbd = Block | Series | Parallel | KofN | PathSets


def block(
    name: str,
    reliability: float | None = None,
    *,
    failure_rate: float | None = None,
    exposure_time: float | None = None,
) -> Block:
    """A block from its reliability, or from a constant failure rate and an exposure time."""
    if reliability is None:
        if failure_rate is None or exposure_time is None:
            raise ValueError(f"{name}: give a reliability, or a failure rate and exposure time")
        reliability = 1.0 - probability_from_rate(failure_rate, exposure_time)
    return Block(name, reliability)


def bridge(r: Sequence[float], name: str = "bridge") -> PathSets:
    """The classical five-component bridge network.

    Components 1 and 2 leave the source, 4 and 5 reach the sink, and 3 is the bridge between
    the two middle nodes (1 → 4, 2 → 5, cross-link 3). Minimal path sets: {1, 4}, {2, 5},
    {1, 3, 5}, {2, 3, 4} (Rausand & Høyland, *System Reliability Theory*, 2nd ed., 2004, §4.6).
    """
    if len(r) != 5:
        raise ValueError("the bridge has five components")
    blocks = tuple(Block(f"c{i + 1}", ri) for i, ri in enumerate(r))
    paths = (("c1", "c4"), ("c2", "c5"), ("c1", "c3", "c5"), ("c2", "c3", "c4"))
    return PathSets(blocks, tuple(frozenset(p) for p in paths), name)


def bridge_reliability(r: Sequence[float]) -> float:
    """Closed-form bridge reliability by pivoting on the cross-link (component 3).

    With component 3 working, the structure is (1 ∥ 2) in series with (4 ∥ 5); with it
    failed, (1–4) ∥ (2–5). For identical components this reduces to
    ``2R^2 + 2R^3 - 5R^4 + 2R^5``.
    """
    r1, r2, r3, r4, r5 = r
    up = (1 - (1 - r1) * (1 - r2)) * (1 - (1 - r4) * (1 - r5))
    down = 1 - (1 - r1 * r4) * (1 - r2 * r5)
    return r3 * up + (1 - r3) * down


def k_out_of_n_identical(k: int, n: int, r: float) -> float:
    """Reliability of a k-out-of-n:G structure of identical, independent blocks."""
    return sum(math.comb(n, j) * r**j * (1 - r) ** (n - j) for j in range(k, n + 1))


def at_least_k(probabilities: Sequence[float], k: int) -> float:
    """P(at least k of independent events occur), by the Poisson-binomial recursion."""
    dist = [1.0]  # dist[j] = P(exactly j of the events seen so far occur)
    for p in probabilities:
        nxt = [0.0] * (len(dist) + 1)
        for j, q in enumerate(dist):
            nxt[j] += q * (1 - p)
            nxt[j + 1] += q * p
        dist = nxt
    return math.fsum(dist[k:])


def _blocks(rbd: Rbd) -> Iterable[Block]:
    if isinstance(rbd, Block):
        yield rbd
    elif isinstance(rbd, PathSets):
        yield from rbd.blocks
    else:
        for child in rbd.children:
            yield from _blocks(child)


def works(rbd: Rbd, working: set[str]) -> bool:
    """Structure function in success logic: does the RBD work when exactly ``working`` work?"""
    if isinstance(rbd, Block):
        return rbd.name in working
    if isinstance(rbd, PathSets):
        return any(path <= working for path in rbd.path_sets)
    count = sum(works(c, working) for c in rbd.children)
    if isinstance(rbd, Series):
        return count == len(rbd.children)
    if isinstance(rbd, Parallel):
        return count >= 1
    return count >= rbd.k


def block_names(rbd: Rbd) -> list[str]:
    """Distinct block names in first-appearance order."""
    return list(dict.fromkeys(b.name for b in _blocks(rbd)))


def reliability(rbd: Rbd) -> float:
    """Closed-form reliability of an RBD whose blocks are distinct and independent.

    A block that appears twice (the same physical component in two places) makes the
    branches dependent and the product formulas wrong, so it is rejected here; convert the
    RBD with :func:`to_unified` and use the exact propagation instead.
    """
    names = [b.name for b in _blocks(rbd)]
    if len(set(names)) != len(names):
        raise ValueError("a block appears more than once; closed forms assume distinct blocks")
    return _reliability(rbd)


def _reliability(rbd: Rbd) -> float:
    if isinstance(rbd, Block):
        return rbd.reliability
    if isinstance(rbd, Series):
        return math.prod(_reliability(c) for c in rbd.children)
    if isinstance(rbd, Parallel):
        return 1.0 - math.prod(1.0 - _reliability(c) for c in rbd.children)
    if isinstance(rbd, KofN):
        return at_least_k([_reliability(c) for c in rbd.children], rbd.k)
    # PathSets: exact enumeration over the 2^n block states (small structures only).
    rel = {b.name: b.reliability for b in rbd.blocks}
    names = list(rel)
    total = 0.0
    for states in itertools.product((False, True), repeat=len(names)):
        up = {n for n, s in zip(names, states, strict=True) if s}
        if any(path <= up for path in rbd.path_sets):
            total += math.prod(
                rel[n] if s else 1 - rel[n] for n, s in zip(names, states, strict=True)
            )
    return total


def to_unified(rbd: Rbd, top: str = "system_failure", description: str = "") -> UnifiedModel:
    """Convert a success-logic RBD into a failure-logic unified model, exactly.

    Each block becomes a physical basic event with probability ``1 - R``; a block name used
    more than once becomes one shared event. Unnamed structures get generated gate names.
    """
    model = UnifiedModel(top, description or "converted from a reliability block diagram")
    counter = itertools.count(1)

    def gate_name(name: str, is_top: bool) -> str:
        if is_top:
            return top
        return name or f"G{next(counter)}"

    def add_block(b: Block) -> str:
        if b.name in model.events:
            if model.events[b.name].probability != 1.0 - b.reliability:
                raise ValueError(f"block {b.name!r} appears with two different reliabilities")
        else:
            model.add_event(physical_event(b.name, probability=1.0 - b.reliability))
        return b.name

    def convert(node: Rbd, is_top: bool = False) -> str:
        if isinstance(node, Block):
            name = add_block(node)
            if is_top:
                model.or_(top, name)
                return top
            return name
        if isinstance(node, PathSets):
            # Failure = every path set is broken = AND over paths of (OR of block failures).
            for b in node.blocks:
                add_block(b)
            gname = gate_name(node.name, is_top)
            path_gates = []
            for path in node.path_sets:
                pg = f"{gname}/path:{'+'.join(sorted(path))}"
                model.or_(pg, *sorted(path))
                path_gates.append(pg)
            model.and_(gname, *path_gates)
            return gname
        gname = gate_name(node.name, is_top)
        children = [convert(c) for c in node.children]
        if isinstance(node, Series):
            model.add_gate(gname, GateType.OR, children)
        elif isinstance(node, Parallel):
            model.add_gate(gname, GateType.AND, children)
        else:
            n = len(node.children)
            model.add_gate(gname, GateType.KOFN, children, k=n - node.k + 1)
        return gname

    convert(rbd, is_top=True)
    return model.validate()
