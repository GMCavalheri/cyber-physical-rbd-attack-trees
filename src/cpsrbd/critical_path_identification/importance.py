r"""Importance measures: which basic events matter most for the top event.

With :math:`Q = P(\text{TOP})`, :math:`Q(1_i)` and :math:`Q(0_i)` the top-event probability with
event :math:`i` forced to happen or made impossible, and :math:`q_i` its probability
(definitions as in Rausand and Høyland, *System Reliability Theory*, 2nd ed., §5.7–5.9):

* **Birnbaum** :math:`I_B(i) = Q(1_i) - Q(0_i) = \partial Q / \partial q_i`: how much the top
  event depends on event :math:`i`.
* **Criticality** :math:`I_{CR}(i) = I_B(i)\,q_i / Q`: the probability that :math:`i` is critical
  and has happened, given the top event happened.
* **Fussell–Vesely** :math:`I_{FV}(i) = P(D_i) / Q`, where :math:`D_i` is "some minimal cut set
  containing :math:`i` has happened": the share of the risk that involves :math:`i`.
* **Risk achievement worth** :math:`RAW(i) = Q(1_i) / Q`: how much worse it gets if :math:`i`
  is certain (the attacker already holds this step; the component is known failed).
* **Risk reduction worth** :math:`RRW(i) = Q / Q(0_i)`: how much better it gets if :math:`i`
  becomes impossible. For a cyber step, :math:`Q(0_i)` is the top-event probability after
  **engineering out** that step, CCE's preferred kind of mitigation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cpsrbd.critical_path_identification.cut_sets import minimal_cut_sets
from cpsrbd.probability_likelihood_propagation import exact_probability
from cpsrbd.unified_graph_model import Origin, UnifiedModel, physical_event


@dataclass(frozen=True)
class Importance:
    event: str
    origin: Origin
    probability: float
    birnbaum: float
    criticality: float
    fussell_vesely: float
    raw: float
    rrw: float
    q_without: float  # Q(0_i): top-event probability with the event engineered out


def _union_probability(model: UnifiedModel, cut_sets: list[frozenset[str]]) -> float:
    """Exact P(at least one of the given cut sets happens)."""
    if not cut_sets:
        return 0.0
    sub = UnifiedModel("union")
    names = sorted(set().union(*cut_sets))
    sub.add_events(physical_event(n, probability=model.events[n].probability) for n in names)
    terms = []
    for j, cs in enumerate(cut_sets):
        if len(cs) == 1:
            terms.append(next(iter(cs)))
        else:
            sub.and_(f"cs{j}", *sorted(cs))
            terms.append(f"cs{j}")
    sub.or_("union", *terms)
    return exact_probability(sub)


def importance_measures(model: UnifiedModel) -> list[Importance]:
    """All five measures for every basic event, sorted by decreasing Fussell–Vesely."""
    q = exact_probability(model)
    if q == 0.0:
        raise ValueError("the top event is impossible; importance is undefined")
    cut_sets = minimal_cut_sets(model)
    rows = []
    for event in model.basic_events():
        name = event.name
        q1 = exact_probability(model, {name: 1.0})
        q0 = exact_probability(model, {name: 0.0})
        birnbaum = q1 - q0
        fv = _union_probability(model, [c for c in cut_sets if name in c]) / q
        rows.append(
            Importance(
                event=name,
                origin=event.origin,
                probability=event.probability,
                birnbaum=birnbaum,
                criticality=birnbaum * event.probability / q,
                fussell_vesely=fv,
                raw=q1 / q,
                rrw=math.inf if q0 == 0.0 else q / q0,
                q_without=q0,
            )
        )
    return sorted(rows, key=lambda r: (-r.fussell_vesely, r.event))
