"""Node types of the unified model: logic gates and basic events.

The model is written in *failure (consequence) logic*: every node stands for an undesired
event, and a node is "true" when that event happens. A gate combines its children's events:

* ``AND`` — the event happens only if **all** children happen (parallel redundancy in an RBD,
  a sequence of required steps in an attack tree);
* ``OR`` — it happens if **any** child happens (series dependency in an RBD, alternative ways
  to reach a goal in an attack tree);
* ``KOFN`` — it happens if **at least k** of its n children happen (voting redundancy).

Basic events are the leaves. Each is tagged with its *origin*: a physical failure (random,
characterised by a failure rate) or a cyber attack step (adversarial, characterised by an
illustrative likelihood score and the attacker's cost).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum


class GateType(StrEnum):
    """Boolean connective of a gate, in failure logic."""

    AND = "AND"
    OR = "OR"
    KOFN = "KOFN"


class Origin(StrEnum):
    """Where a basic event comes from."""

    PHYSICAL = "physical"
    CYBER = "cyber"


@dataclass(frozen=True)
class Gate:
    """An intermediate event defined by a Boolean function of its children.

    ``children`` is ordered (the order is kept for plotting and reports). ``k`` is required
    for ``KOFN`` gates and must satisfy ``1 <= k <= len(children)``.
    """

    name: str
    kind: GateType
    children: tuple[str, ...]
    k: int | None = None
    description: str = ""

    def threshold(self) -> int:
        """Number of children that must occur for the gate to occur."""
        if self.kind is GateType.AND:
            return len(self.children)
        if self.kind is GateType.OR:
            return 1
        assert self.k is not None
        return self.k


@dataclass(frozen=True)
class BasicEvent:
    """A leaf: an independent Bernoulli event over the analysis window.

    ``probability`` is the chance that the event occurs within the window.

    ``cost`` is the attacker's effort to make the event happen, in arbitrary but consistent
    units (for example analyst-weeks). It is meaningful only for cyber steps; a physical
    failure cannot be bought by the attacker, so its cost is ``math.inf``.

    ``attributes`` carries free-form metadata (failure rate, exposure time, likelihood scores,
    ATT&CK for ICS technique, source of the number) for reports.
    """

    name: str
    origin: Origin
    probability: float
    cost: float = math.inf
    description: str = ""
    attributes: dict[str, str | float] = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self) -> None:
        if not 0.0 <= self.probability <= 1.0 or math.isnan(self.probability):
            raise ValueError(f"{self.name}: probability {self.probability} is not in [0, 1]")
        if math.isnan(self.cost) or self.cost < 0.0:
            raise ValueError(f"{self.name}: cost {self.cost} must be >= 0")


def probability_from_rate(failure_rate: float, exposure_time: float) -> float:
    """Probability of at least one failure of an exponential component within ``exposure_time``.

    ``P = 1 - exp(-lambda * t)`` (constant failure rate, no repair inside the window).
    """
    if failure_rate < 0.0 or exposure_time < 0.0:
        raise ValueError("failure rate and exposure time must be >= 0")
    return -math.expm1(-failure_rate * exposure_time)


def physical_event(
    name: str,
    *,
    probability: float | None = None,
    failure_rate: float | None = None,
    exposure_time: float | None = None,
    description: str = "",
    source: str = "",
) -> BasicEvent:
    """Build a physical failure, either from a probability or from a rate and exposure time."""
    attributes: dict[str, str | float] = {}
    if probability is None:
        if failure_rate is None or exposure_time is None:
            raise ValueError(f"{name}: give a probability, or a failure rate and exposure time")
        probability = probability_from_rate(failure_rate, exposure_time)
        attributes |= {"failure_rate": failure_rate, "exposure_time": exposure_time}
    elif failure_rate is not None or exposure_time is not None:
        raise ValueError(f"{name}: give a probability or a rate, not both")
    if source:
        attributes["source"] = source
    return BasicEvent(name, Origin.PHYSICAL, probability, math.inf, description, attributes)


def cyber_step(
    name: str,
    *,
    probability: float,
    cost: float,
    description: str = "",
    technique: str = "",
    source: str = "",
    **scores: float,
) -> BasicEvent:
    """Build a cyber attack step from a likelihood (see ``likelihood``) and an attacker cost."""
    attributes: dict[str, str | float] = dict(scores)
    if technique:
        attributes["technique"] = technique
    if source:
        attributes["source"] = source
    return BasicEvent(name, Origin.CYBER, probability, cost, description, attributes)
