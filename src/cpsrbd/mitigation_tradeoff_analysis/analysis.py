"""Compare mitigations and portfolios on one model; test how robust the comparison is.

Two yardsticks are used throughout, because CCE cares about both:

* **risk**: the exact top-event probability per window (lower is better);
* **attacker effort**: the exact minimum cost of an attacker-controlled path to the top event
  (higher is better; infinite when no purely cyber path remains).

Sensitivity tools:

* :func:`tornado` moves one basic event's probability down and up by a factor and records the
  top-event probability (one-at-a-time sensitivity);
* :func:`uncertainty_samples` redraws every probability from a lognormal distribution around
  its nominal value (median = nominal, given error factor) and re-evaluates every option on
  each draw, so one can ask how often a ranking survives the uncertainty in the inputs.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass, replace

import numpy as np

from cpsrbd.critical_path_identification import min_attacker_cost
from cpsrbd.mitigation_tradeoff_analysis.mitigations import Mitigation, apply_all
from cpsrbd.probability_likelihood_propagation import exact_probability
from cpsrbd.unified_graph_model import Origin, UnifiedModel

Z95 = 1.6448536269514722  # standard normal 95th percentile


@dataclass(frozen=True)
class Assessment:
    """The effect of one option (a mitigation or a portfolio) on the two yardsticks."""

    name: str
    investment: float
    q_before: float
    q_after: float
    cost_before: float
    cost_after: float

    @property
    def risk_reduction(self) -> float:
        """Relative reduction of the top-event probability, 0..1."""
        return 1.0 - self.q_after / self.q_before

    @property
    def reduction_per_investment(self) -> float:
        return math.inf if self.investment == 0 else self.risk_reduction / self.investment

    @property
    def effort_gain(self) -> float:
        """Factor by which the attacker's cheapest path became more expensive."""
        if math.isinf(self.cost_after):
            return math.inf
        return self.cost_after / self.cost_before


def assess(model: UnifiedModel, mitigations: Sequence[Mitigation]) -> list[Assessment]:
    """Each mitigation on its own, against the unmitigated model."""
    q0 = exact_probability(model)
    c0 = min_attacker_cost(model)
    out = []
    for m in mitigations:
        after = m.apply(model)
        out.append(
            Assessment(
                m.name, m.investment, q0, exact_probability(after), c0, min_attacker_cost(after)
            )
        )
    return out


@dataclass(frozen=True)
class Portfolio:
    names: tuple[str, ...]
    investment: float
    q: float
    attacker_cost: float
    physical_share: float  # fraction of the investment spent on physical options


def portfolios(model: UnifiedModel, mitigations: Sequence[Mitigation]) -> list[Portfolio]:
    """Every subset of the mitigations (2^n of them), evaluated exactly."""
    if len(mitigations) > 12:
        raise ValueError("more than 12 options: enumerate a shortlist instead")
    out = []
    for r in range(len(mitigations) + 1):
        for subset in itertools.combinations(mitigations, r):
            m = apply_all(model, subset)
            spend = math.fsum(s.investment for s in subset)
            physical = math.fsum(s.investment for s in subset if s.category == "physical")
            out.append(
                Portfolio(
                    tuple(s.name for s in subset),
                    spend,
                    exact_probability(m),
                    min_attacker_cost(m),
                    physical / spend if spend else 0.0,
                )
            )
    return out


def pareto_front(options: Sequence[Portfolio], objective: str = "risk") -> list[Portfolio]:
    """Non-dominated portfolios: less investment and (lower risk | higher attacker cost)."""

    def better(a: Portfolio, b: Portfolio) -> bool:
        if objective == "risk":
            no_worse = a.investment <= b.investment and a.q <= b.q
            strictly = a.investment < b.investment or a.q < b.q
        elif objective == "effort":
            no_worse = a.investment <= b.investment and a.attacker_cost >= b.attacker_cost
            strictly = a.investment < b.investment or a.attacker_cost > b.attacker_cost
        else:
            raise ValueError("objective is 'risk' or 'effort'")
        return no_worse and strictly

    front = [p for p in options if not any(better(o, p) for o in options)]
    return sorted(front, key=lambda p: (p.investment, p.q, p.names))


def best_within_budget(
    options: Sequence[Portfolio], budget: float, objective: str = "risk"
) -> Portfolio:
    """The best portfolio that fits the budget (ties broken by lower investment)."""
    feasible = [p for p in options if p.investment <= budget]
    if objective == "risk":
        return min(feasible, key=lambda p: (p.q, p.investment, p.names))
    return max(feasible, key=lambda p: (p.attacker_cost, -p.q, -p.investment, p.names))


@dataclass(frozen=True)
class TornadoBar:
    event: str
    origin: Origin
    q_low: float  # top-event probability with the event's probability divided by the factor
    q_high: float  # ... multiplied by the factor (capped at 1)

    @property
    def swing(self) -> float:
        return self.q_high - self.q_low


def tornado(model: UnifiedModel, factor: float = 3.0) -> list[TornadoBar]:
    """One-at-a-time sensitivity of P(TOP) to each event's probability (÷/× ``factor``)."""
    if factor < 1.0:
        raise ValueError("factor must be >= 1")
    bars = []
    for e in model.basic_events():
        low = exact_probability(model, {e.name: e.probability / factor})
        high = exact_probability(model, {e.name: min(1.0, e.probability * factor)})
        bars.append(TornadoBar(e.name, e.origin, low, high))
    return sorted(bars, key=lambda b: (-b.swing, b.event))


def perturbed(
    model: UnifiedModel,
    rng: np.random.Generator,
    physical_error_factor: float = 3.0,
    cyber_error_factor: float = 10.0,
) -> UnifiedModel:
    """A copy with every probability redrawn from a lognormal around its nominal value.

    The error factor EF is the ratio of the 95th percentile to the median, so
    ``sigma = ln(EF) / 1.645`` (the convention of probabilistic risk assessment). Draws are
    capped at 1. Cyber steps get a wider default spread than physical failures, reflecting
    judgement-based inputs.
    """
    out = model
    for e in model.basic_events():
        ef = cyber_error_factor if e.origin is Origin.CYBER else physical_error_factor
        if ef < 1.0:
            raise ValueError("error factors must be >= 1")
        sigma = math.log(ef) / Z95
        p = min(1.0, e.probability * math.exp(sigma * rng.standard_normal()))
        out = out.with_event(replace(e, probability=p))
    return out


def uncertainty_samples(
    model: UnifiedModel,
    mitigations: Sequence[Mitigation],
    samples: int = 500,
    seed: int = 0,
    physical_error_factor: float = 3.0,
    cyber_error_factor: float = 10.0,
) -> dict[str, np.ndarray]:
    """Risk reduction of each mitigation (and the baseline P(TOP)) over perturbed inputs.

    Returns arrays of length ``samples``: ``"baseline"`` holds P(TOP) without mitigation, and
    each mitigation's name holds its relative risk reduction on the same draw, so options are
    compared on common random numbers.
    """
    rng = np.random.default_rng(seed)
    out: dict[str, np.ndarray] = {"baseline": np.empty(samples)}
    for m in mitigations:
        out[m.name] = np.empty(samples)
    for i in range(samples):
        draw = perturbed(model, rng, physical_error_factor, cyber_error_factor)
        q0 = exact_probability(draw)
        out["baseline"][i] = q0
        for m in mitigations:
            out[m.name][i] = 1.0 - exact_probability(m.apply(draw)) / q0
    return out
