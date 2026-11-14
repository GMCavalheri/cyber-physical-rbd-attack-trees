"""Consequence-first model construction and structural queries.

CCE starts from a consequence the organisation cannot tolerate and works *backward*: which
functions must be lost for it to happen, what those functions depend on, and which physical
failures or adversary actions could remove each dependency. :class:`ConsequenceBuilder` writes
a model in that order — top event first, then each cause developed into its own causes — and
refuses to build while any referenced cause is left undeveloped, so the analysis cannot stop
halfway down a branch without saying so.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from cpsrbd.unified_graph_model import BasicEvent, GateType, ModelError, Origin, UnifiedModel


@dataclass(frozen=True)
class Consequence:
    """The top event: a named, unacceptable outcome stated in plain words."""

    name: str
    statement: str


class ConsequenceBuilder:
    """Develop a consequence top-down into causes, ending in basic events."""

    def __init__(self, consequence: Consequence) -> None:
        self.consequence = consequence
        self._model = UnifiedModel(consequence.name, consequence.statement)
        self._referenced: dict[str, str] = {}  # cause -> the node that referenced it first

    def _develop(
        self, node: str, kind: GateType, causes: Iterable[str], k: int | None, description: str
    ) -> ConsequenceBuilder:
        causes = tuple(causes)
        if node != self.consequence.name and node not in self._referenced:
            raise ModelError(f"{node!r} is developed before any node refers to it as a cause")
        self._model.add_gate(node, kind, causes, k=k, description=description)
        for cause in causes:
            self._referenced.setdefault(cause, node)
        return self

    def any_of(self, node: str, *causes: str, description: str = "") -> ConsequenceBuilder:
        """``node`` happens if any cause happens (OR)."""
        return self._develop(node, GateType.OR, causes, None, description)

    def all_of(self, node: str, *causes: str, description: str = "") -> ConsequenceBuilder:
        """``node`` happens only if all causes happen (AND)."""
        return self._develop(node, GateType.AND, causes, None, description)

    def at_least(
        self, node: str, k: int, *causes: str, description: str = ""
    ) -> ConsequenceBuilder:
        """``node`` happens if at least ``k`` causes happen."""
        return self._develop(node, GateType.KOFN, causes, k, description)

    def events(self, events: Iterable[BasicEvent]) -> ConsequenceBuilder:
        for event in events:
            self._model.add_event(event)
        return self

    def undeveloped(self) -> list[str]:
        """Causes referenced so far that are neither developed nor a basic event."""
        return sorted(c for c in self._referenced if c not in self._model)

    def build(self) -> UnifiedModel:
        missing = self.undeveloped()
        if missing:
            raise ModelError(f"undeveloped causes: {missing}")
        return self._model.validate()


class BranchKind(StrEnum):
    """What can trigger a gate: physical failures only, cyber steps only, or both."""

    PHYSICAL = "physical-only"
    CYBER = "cyber-only"
    MIXED = "mixed"


def branch_origins(model: UnifiedModel) -> dict[str, set[Origin]]:
    """For every reachable node, the origins of the basic events below it."""
    below: dict[str, set[Origin]] = {}
    for name in model.bottom_up():
        if name in model.events:
            below[name] = {model.events[name].origin}
        else:
            below[name] = set().union(*(below[c] for c in model.children(name)))
    return below


def branch_kinds(model: UnifiedModel) -> dict[str, BranchKind]:
    """Classify every gate as physical-only, cyber-only or mixed."""
    kinds: dict[str, BranchKind] = {}
    for name, origins in branch_origins(model).items():
        if name not in model.gates:
            continue
        if origins == {Origin.PHYSICAL}:
            kinds[name] = BranchKind.PHYSICAL
        elif origins == {Origin.CYBER}:
            kinds[name] = BranchKind.CYBER
        else:
            kinds[name] = BranchKind.MIXED
    return kinds


def paths_to(model: UnifiedModel, node: str) -> list[list[str]]:
    """Every path from the top event down to ``node`` (top first), in child order.

    Reading these paths is the backward walk of CCE: from the consequence, through the
    functions and dependencies, to one failure or attack step.
    """
    if node not in model:
        raise ModelError(f"no node named {node!r}")
    paths: list[list[str]] = []

    def walk(name: str, path: list[str]) -> None:
        path = [*path, name]
        if name == node:
            paths.append(path)
            return
        for child in model.children(name):
            walk(child, path)

    walk(model.top, [])
    return paths
