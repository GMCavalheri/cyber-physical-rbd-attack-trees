"""The unified model: one DAG of gates and basic events rooted at a top-event consequence."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from functools import cache

import networkx as nx

from cpsrbd.unified_graph_model.nodes import BasicEvent, Gate, GateType, Origin


class ModelError(ValueError):
    """The model is not a well-formed single-rooted DAG of valid gates and events."""


class UnifiedModel:
    """A directed acyclic graph of gates over basic events, with one top event.

    Nodes are referenced by unique names. A node may have several parents (a shared
    dependency such as a common power supply, or an attack step that serves two goals), so the
    structure is a DAG rather than a tree; the analyses handle the dependence this creates.

    Build it with :meth:`add_event` and :meth:`add_gate` (or the ``and_`` / ``or_`` / ``kofn``
    shortcuts), then call :meth:`validate`. Analyses validate the model they receive.
    """

    def __init__(self, top: str, description: str = "") -> None:
        self.top = top
        self.description = description
        self.gates: dict[str, Gate] = {}
        self.events: dict[str, BasicEvent] = {}

    # ----------------------------------------------------------------- construction
    def add_event(self, event: BasicEvent) -> UnifiedModel:
        self._check_new(event.name)
        self.events[event.name] = event
        return self

    def add_events(self, events: Iterable[BasicEvent]) -> UnifiedModel:
        for event in events:
            self.add_event(event)
        return self

    def add_gate(
        self,
        name: str,
        kind: GateType,
        children: Iterable[str],
        k: int | None = None,
        description: str = "",
    ) -> UnifiedModel:
        self._check_new(name)
        self.gates[name] = Gate(name, kind, tuple(children), k, description)
        return self

    def and_(self, name: str, *children: str, description: str = "") -> UnifiedModel:
        return self.add_gate(name, GateType.AND, children, description=description)

    def or_(self, name: str, *children: str, description: str = "") -> UnifiedModel:
        return self.add_gate(name, GateType.OR, children, description=description)

    def kofn(self, name: str, k: int, *children: str, description: str = "") -> UnifiedModel:
        return self.add_gate(name, GateType.KOFN, children, k=k, description=description)

    def _check_new(self, name: str) -> None:
        if not name:
            raise ModelError("node names must be non-empty")
        if name in self.gates or name in self.events:
            raise ModelError(f"duplicate node name {name!r}")

    # ----------------------------------------------------------------- editing (copies)
    def copy(self) -> UnifiedModel:
        other = UnifiedModel(self.top, self.description)
        other.gates = dict(self.gates)
        other.events = dict(self.events)
        return other

    def with_event(self, event: BasicEvent) -> UnifiedModel:
        """A copy with the basic event of the same name replaced."""
        if event.name not in self.events:
            raise ModelError(f"no basic event named {event.name!r}")
        other = self.copy()
        other.events[event.name] = event
        return other

    def with_gate(self, gate: Gate) -> UnifiedModel:
        """A copy with the gate of the same name replaced (or a basic event turned into it)."""
        if gate.name not in self.gates and gate.name not in self.events:
            raise ModelError(f"no node named {gate.name!r}")
        other = self.copy()
        other.events.pop(gate.name, None)
        other.gates[gate.name] = gate
        return other

    def pruned(self) -> UnifiedModel:
        """A copy without the nodes that the top event no longer reaches."""
        keep = set(self.reachable())
        other = UnifiedModel(self.top, self.description)
        other.gates = {n: g for n, g in self.gates.items() if n in keep}
        other.events = {n: e for n, e in self.events.items() if n in keep}
        return other

    # ----------------------------------------------------------------- queries
    def __contains__(self, name: object) -> bool:
        return name in self.gates or name in self.events

    def __len__(self) -> int:
        return len(self.gates) + len(self.events)

    def node(self, name: str) -> Gate | BasicEvent:
        if name in self.gates:
            return self.gates[name]
        if name in self.events:
            return self.events[name]
        raise ModelError(f"no node named {name!r}")

    def is_gate(self, name: str) -> bool:
        return name in self.gates

    def children(self, name: str) -> tuple[str, ...]:
        return self.gates[name].children if name in self.gates else ()

    def reachable(self) -> Iterator[str]:
        """Nodes reachable from the top event (the top included), each once."""
        seen: set[str] = set()
        stack = [self.top]
        while stack:
            name = stack.pop()
            if name in seen:
                continue
            seen.add(name)
            yield name
            stack.extend(self.children(name))

    def basic_events(self) -> list[BasicEvent]:
        """The basic events the top event depends on, sorted by name."""
        return [self.events[n] for n in sorted(self.reachable()) if n in self.events]

    def origins(self) -> set[Origin]:
        return {e.origin for e in self.basic_events()}

    def bottom_up(self) -> list[str]:
        """Reachable nodes ordered so that every child precedes its parents."""
        order: list[str] = []
        done: set[str] = set()

        def visit(name: str) -> None:
            if name in done:
                return
            for child in self.children(name):
                visit(child)
            done.add(name)
            order.append(name)

        visit(self.top)
        return order

    def path_counts(self) -> dict[str, int]:
        """Number of distinct paths from the top event to each reachable node.

        A node with more than one path is *shared*: its event influences the top event through
        several routes, which makes the routes statistically dependent.
        """
        counts = dict.fromkeys(self.reachable(), 0)
        counts[self.top] = 1
        for name in reversed(self.bottom_up()):  # parents before children
            for child in self.children(name):
                counts[child] += counts[name]
        return counts

    def shared_events(self) -> list[str]:
        """Basic events reachable from the top through more than one path, sorted by name."""
        return sorted(n for n, c in self.path_counts().items() if c > 1 and n in self.events)

    def is_tree(self) -> bool:
        return all(c == 1 for c in self.path_counts().values())

    # ----------------------------------------------------------------- semantics
    def structure_function(self, failed: Mapping[str, bool]) -> bool:
        """Whether the top event happens for the given states of the basic events.

        ``failed[name]`` is True when basic event ``name`` occurs. This is the Boolean
        structure function of the model (in failure logic).
        """

        @cache
        def value(name: str) -> bool:
            if name in self.events:
                return bool(failed[name])
            gate = self.gates[name]
            count = sum(value(child) for child in gate.children)
            return count >= gate.threshold()

        return value(self.top)

    # ----------------------------------------------------------------- validation
    def validate(self) -> UnifiedModel:
        """Check the model is a well-formed DAG with one top event; return it for chaining."""
        if self.top not in self:
            raise ModelError(f"top event {self.top!r} is not defined")
        for gate in self.gates.values():
            if not gate.children:
                raise ModelError(f"gate {gate.name!r} has no children")
            if len(set(gate.children)) != len(gate.children):
                raise ModelError(f"gate {gate.name!r} lists a child twice")
            for child in gate.children:
                if child not in self:
                    raise ModelError(f"gate {gate.name!r} refers to undefined node {child!r}")
            if gate.kind is GateType.KOFN:
                if gate.k is None or not 1 <= gate.k <= len(gate.children):
                    raise ModelError(
                        f"gate {gate.name!r}: k = {gate.k} must be in 1..{len(gate.children)}"
                    )
            elif gate.k is not None:
                raise ModelError(f"gate {gate.name!r}: k is only meaningful for KOFN gates")
        graph = self.graph()
        if not nx.is_directed_acyclic_graph(graph):
            cycle = nx.find_cycle(graph)
            raise ModelError(f"the model has a cycle: {cycle}")
        parents = {n for n, d in graph.in_degree() if d == 0}
        if parents != {self.top}:
            extra = sorted(parents - {self.top})
            raise ModelError(f"nodes not reachable from the top event: {extra}")
        return self

    def graph(self) -> nx.DiGraph[str]:
        """The model as a NetworkX DiGraph, edges from parent to child.

        Node attributes: ``kind`` ("AND"/"OR"/"KOFN"/"event"), ``origin`` for basic events,
        ``k`` for KOFN gates, ``probability`` and ``cost`` for basic events.
        """
        graph: nx.DiGraph[str] = nx.DiGraph()
        for gate in self.gates.values():
            graph.add_node(gate.name, kind=str(gate.kind), k=gate.k)
            for child in gate.children:
                graph.add_edge(gate.name, child)
        for event in self.events.values():
            graph.add_node(
                event.name,
                kind="event",
                origin=str(event.origin),
                probability=event.probability,
                cost=event.cost,
            )
        return graph

    def summary(self) -> str:
        events = self.basic_events()
        physical = sum(e.origin is Origin.PHYSICAL for e in events)
        gates = len([n for n in self.reachable() if n in self.gates])
        return (
            f"UnifiedModel(top={self.top!r}: {gates} gates, {physical} physical events, "
            f"{len(events) - physical} cyber steps, shared events {len(self.shared_events())})"
        )

    def __repr__(self) -> str:
        return self.summary()
