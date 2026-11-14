r"""Top-event probability: bottom-up, exact (Shannon decomposition), enumeration, Monte Carlo.

All methods assume the basic events are independent Bernoulli variables with the
probabilities stored on the model (or overridden by the caller).

* :func:`bottom_up_probability` combines children with the independence formulas
  (AND: product, OR: complement of the product of complements, k-of-n: Poisson-binomial tail).
  It is **exact on trees**. On a DAG, two children of a gate can depend on the same basic
  event, so they are not independent and the result is only an approximation.
* :func:`exact_probability` is exact on any DAG. It conditions on the *shared* basic events
  (those reached by more than one path) one at a time, using Shannon's expansion

  .. math::

      P(\text{TOP}) = p_x\,P(\text{TOP} \mid x = 1) + (1 - p_x)\,P(\text{TOP} \mid x = 0),

  until every shared event is fixed. Then every remaining basic event is reached by exactly
  one path, so the children of every gate depend on disjoint sets of free events (and a shared
  gate depends only on fixed events, so it is a constant): the bottom-up formulas are exact
  again. The cost is :math:`2^s` bottom-up passes for :math:`s` shared events.
* :func:`enumerate_probability` sums the structure function over all :math:`2^n` states. It is
  the independent oracle used by the tests; it only scales to about 20 events.
* :func:`monte_carlo_probability` samples states and reports a Wilson score interval.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from cpsrbd.rbd import at_least_k
from cpsrbd.unified_graph_model import GateType, Origin, UnifiedModel

MAX_SHARED = 22
MAX_ENUMERATED = 22


def _leaf_probabilities(
    model: UnifiedModel, overrides: Mapping[str, float] | None
) -> dict[str, float]:
    probs = {e.name: e.probability for e in model.basic_events()}
    if overrides:
        for name, p in overrides.items():
            if name not in probs:
                raise KeyError(f"no basic event named {name!r}")
            probs[name] = p
    return probs


def gate_probability(kind: GateType, child_probs: list[float], k: int | None = None) -> float:
    """Probability of a gate whose children are independent with the given probabilities."""
    if kind is GateType.AND:
        return math.prod(child_probs)
    if kind is GateType.OR:
        return 1.0 - math.prod(1.0 - p for p in child_probs)
    assert k is not None
    return at_least_k(child_probs, k)


def node_probabilities(
    model: UnifiedModel, overrides: Mapping[str, float] | None = None
) -> dict[str, float]:
    """Bottom-up probability of every reachable node (independence formulas at each gate)."""
    probs: dict[str, float] = dict(_leaf_probabilities(model, overrides))
    for name in model.bottom_up():
        if name in model.gates:
            gate = model.gates[name]
            probs[name] = gate_probability(gate.kind, [probs[c] for c in gate.children], gate.k)
    return probs


def bottom_up_probability(
    model: UnifiedModel, overrides: Mapping[str, float] | None = None
) -> float:
    """Top-event probability by the independence formulas: exact on trees only."""
    return node_probabilities(model, overrides)[model.top]


def exact_probability(model: UnifiedModel, overrides: Mapping[str, float] | None = None) -> float:
    """Exact top-event probability on any DAG, by Shannon decomposition on shared events."""
    model.validate()
    probs = _leaf_probabilities(model, overrides)
    shared = model.shared_events()
    if len(shared) > MAX_SHARED:
        raise ValueError(f"{len(shared)} shared events: 2^{len(shared)} passes is too many")
    total = 0.0
    for states in itertools.product((True, False), repeat=len(shared)):
        weight = 1.0
        fixed: dict[str, float] = dict(probs)
        for name, state in zip(shared, states, strict=True):
            weight *= probs[name] if state else 1.0 - probs[name]
            fixed[name] = 1.0 if state else 0.0
        if weight == 0.0:
            continue
        total += weight * bottom_up_probability(model, fixed)
    return total


def conditional_probability(
    model: UnifiedModel,
    given: Mapping[str, bool],
    overrides: Mapping[str, float] | None = None,
) -> float:
    """Exact P(TOP | the listed basic events are in the given states)."""
    fixed = dict(overrides or {})
    fixed.update({n: 1.0 if s else 0.0 for n, s in given.items()})
    return exact_probability(model, fixed)


def enumerate_probability(
    model: UnifiedModel, overrides: Mapping[str, float] | None = None
) -> float:
    """Oracle: sum the structure function over every state of every basic event."""
    model.validate()
    probs = _leaf_probabilities(model, overrides)
    names = list(probs)
    if len(names) > MAX_ENUMERATED:
        raise ValueError(f"{len(names)} events: 2^{len(names)} states is too many to enumerate")
    total = 0.0
    for states in itertools.product((False, True), repeat=len(names)):
        failed = dict(zip(names, states, strict=True))
        if model.structure_function(failed):
            total += math.prod(probs[n] if s else 1.0 - probs[n] for n, s in failed.items())
    return total


@dataclass(frozen=True)
class MonteCarloResult:
    estimate: float
    low: float
    high: float
    samples: int
    hits: int


def wilson_interval(hits: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (95 % by default)."""
    if n <= 0:
        raise ValueError("need at least one sample")
    phat = hits / n
    denom = 1 + z * z / n
    centre = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def monte_carlo_probability(
    model: UnifiedModel,
    samples: int = 1_000_000,
    seed: int = 0,
    overrides: Mapping[str, float] | None = None,
    batch: int = 250_000,
) -> MonteCarloResult:
    """Estimate P(TOP) by sampling independent event states (vectorised, seeded)."""
    model.validate()
    probs = _leaf_probabilities(model, overrides)
    rng = np.random.default_rng(seed)
    order = model.bottom_up()
    hits = 0
    done = 0
    while done < samples:
        n = min(batch, samples - done)
        state: dict[str, np.ndarray] = {}
        for name in sorted(probs):  # fixed order: reproducible for a given seed
            state[name] = rng.random(n) < probs[name]
        for name in order:
            if name in model.gates:
                gate = model.gates[name]
                count = np.sum([state[c] for c in gate.children], axis=0)
                state[name] = count >= gate.threshold()
        hits += int(state[model.top].sum())
        done += n
    low, high = wilson_interval(hits, samples)
    return MonteCarloResult(hits / samples, low, high, samples, hits)


def origin_overrides(model: UnifiedModel, keep: Origin) -> dict[str, float]:
    """Overrides that switch off every basic event whose origin is not ``keep``.

    ``exact_probability(model, origin_overrides(model, Origin.PHYSICAL))`` is the top-event
    probability with no attack (the classical reliability view); with ``Origin.CYBER`` it is
    the attack-only view with perfect hardware.
    """
    return {e.name: 0.0 for e in model.basic_events() if e.origin is not keep}


@dataclass(frozen=True)
class OriginDecomposition:
    """What each partial view of a mixed model sees, and the interaction gap between them.

    ``physical`` is P(TOP) with every cyber step switched off (the reliability view), ``cyber``
    with every physical failure switched off (the attack-tree view), ``separate`` is what the
    two views give when combined as independent risks, ``1 - (1 - physical)(1 - cyber)``, and
    ``gap = full - separate`` is the probability that the top event happens *only* through
    mixed scenarios, which neither view contains (Proposition 5 in docs/formal-semantics.md:
    it is never negative).
    """

    full: float
    physical: float
    cyber: float

    @property
    def separate(self) -> float:
        return 1.0 - (1.0 - self.physical) * (1.0 - self.cyber)

    @property
    def gap(self) -> float:
        return self.full - self.separate

    @property
    def gap_share(self) -> float:
        return 0.0 if self.full == 0.0 else self.gap / self.full


def origin_decomposition(model: UnifiedModel) -> OriginDecomposition:
    """Exact full, physical-only and cyber-only top-event probabilities."""
    return OriginDecomposition(
        exact_probability(model),
        exact_probability(model, origin_overrides(model, Origin.PHYSICAL)),
        exact_probability(model, origin_overrides(model, Origin.CYBER)),
    )
