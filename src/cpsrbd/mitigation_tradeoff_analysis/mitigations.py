"""Mitigations as model transformations, so physical and cyber options share one yardstick.

Every mitigation is a function from a model to a modified copy. The four kinds cover the
options a CCE Phase 4 discussion produces:

* :class:`AddRedundancy` — duplicate a physical component: the event becomes "both units
  fail", optionally with a beta-factor common-cause term (a fraction ``beta`` of the failure
  probability hits both units at once), the standard way to keep redundancy honest.
* :class:`ReduceProbability` — make an event less likely (better detection, hardening,
  monitoring) and, for a cyber step, more expensive for the attacker.
* :class:`RequireStep` — put a new, required attack step in front of an existing one (network
  segmentation, message authentication, a bus guardian): the old step now needs AND the new
  one.
* :class:`EngineerOut` — remove a digital dependency so the step can no longer happen at all
  (CCE's preferred mitigation).

``investment`` is in arbitrary but consistent cost units (assumptions, like everything in the
case study), and ``category`` says whether the option is a physical or a cyber investment.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum

from cpsrbd.unified_graph_model import (
    BasicEvent,
    Gate,
    GateType,
    ModelError,
    Origin,
    UnifiedModel,
)


class Category(StrEnum):
    PHYSICAL = "physical"
    CYBER = "cyber"
    ENGINEER_OUT = "engineer-out"


@dataclass(frozen=True)
class Mitigation:
    """Base class: a named, costed change to the model."""

    name: str
    investment: float
    category: Category
    description: str = field(default="", kw_only=True)
    basis: str = field(default="assumption", kw_only=True)

    def apply(self, model: UnifiedModel) -> UnifiedModel:
        raise NotImplementedError

    def _event(self, model: UnifiedModel, name: str) -> BasicEvent:
        if name not in model.events:
            raise ModelError(f"{self.name}: no basic event named {name!r}")
        return model.events[name]


@dataclass(frozen=True)
class AddRedundancy(Mitigation):
    """Duplicate the physical components ``events`` (independent units, optional beta factor).

    Each event ``e`` with probability ``q`` becomes a gate named ``e`` (so its parents are
    unchanged) over two units ``e/unit_a`` and ``e/unit_b`` with probability ``(1 - beta) q``
    each, OR'ed with a common-cause event ``e/ccf`` of probability ``beta q`` when
    ``beta > 0``. With ``beta = 1`` the duplicate buys nothing.
    """

    events: tuple[str, ...] = ()
    beta: float = 0.0

    def apply(self, model: UnifiedModel) -> UnifiedModel:
        if not 0.0 <= self.beta <= 1.0:
            raise ValueError("beta must be in [0, 1]")
        out = model
        for name in self.events:
            event = self._event(out, name)
            if event.origin is not Origin.PHYSICAL:
                raise ModelError(f"{self.name}: redundancy applies to physical events only")
            q = event.probability
            units = [
                replace(event, name=f"{name}/unit_{u}", probability=(1 - self.beta) * q)
                for u in "ab"
            ]
            out = out.copy()
            del out.events[name]
            out.add_events(units)
            pair = (units[0].name, units[1].name)
            if self.beta > 0.0:
                out.add_event(replace(event, name=f"{name}/ccf", probability=self.beta * q))
                out.add_gate(f"{name}/independent", GateType.AND, pair)
                out.add_gate(name, GateType.OR, (f"{name}/independent", f"{name}/ccf"))
            else:
                out.add_gate(name, GateType.AND, pair)
        return out.validate()


@dataclass(frozen=True)
class ReduceProbability(Mitigation):
    """Multiply the probability of ``event`` by ``factor`` and add ``added_cost`` to its cost."""

    event: str = ""
    factor: float = 1.0
    added_cost: float = 0.0

    def apply(self, model: UnifiedModel) -> UnifiedModel:
        if not 0.0 <= self.factor <= 1.0 or self.added_cost < 0.0:
            raise ValueError("factor must be in [0, 1] and added_cost >= 0")
        e = self._event(model, self.event)
        return model.with_event(
            replace(e, probability=e.probability * self.factor, cost=e.cost + self.added_cost)
        )


@dataclass(frozen=True)
class RequireStep(Mitigation):
    """Make ``target`` (an event or gate) also require the new cyber step ``step``.

    Every parent of ``target`` is rewired to a new AND gate ``target+step.name`` over
    ``target`` and ``step``.
    """

    target: str = ""
    step: BasicEvent | None = None

    def apply(self, model: UnifiedModel) -> UnifiedModel:
        if self.step is None or self.target not in model:
            raise ModelError(f"{self.name}: needs a step and an existing target")
        guarded = f"{self.target}+{self.step.name}"
        out = model.copy()
        out.add_event(self.step)
        out.add_gate(guarded, GateType.AND, (self.target, self.step.name))
        for name, gate in model.gates.items():
            if self.target in gate.children:
                kids = tuple(guarded if c == self.target else c for c in gate.children)
                out.gates[name] = Gate(name, gate.kind, kids, gate.k, gate.description)
        if out.top == self.target:
            out.top = guarded
        return out.validate()


@dataclass(frozen=True)
class EngineerOut(Mitigation):
    """Remove the dependency: the listed events can no longer happen (p = 0, cost = ∞)."""

    events: tuple[str, ...] = ()

    def apply(self, model: UnifiedModel) -> UnifiedModel:
        out = model
        for name in self.events:
            e = self._event(out, name)
            out = out.with_event(replace(e, probability=0.0, cost=math.inf))
        return out


def apply_all(model: UnifiedModel, mitigations: Sequence[Mitigation]) -> UnifiedModel:
    """Apply several mitigations in order."""
    for m in mitigations:
        model = m.apply(model)
    return model
