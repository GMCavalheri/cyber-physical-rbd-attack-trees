"""Phase 4: minimal cut sets, the lowest-effort paths and importance in the case study."""

from __future__ import annotations

import math
from dataclasses import replace

import matplotlib.pyplot as plt

from cpsrbd import plotting
from cpsrbd.consequence_driven_analysis import navigation_case_study
from cpsrbd.critical_path_identification import (
    PathKind,
    activated,
    cheapest_attacks,
    describe,
    importance_measures,
    min_attacker_cost,
    most_likely,
    opportunistic_front,
)
from cpsrbd.probability_likelihood_propagation import MIN_COST, evaluate, exact_probability
from cpsrbd.unified_graph_model import BasicEvent, Origin, UnifiedModel

from common import FIGURES, table, write_result

KIND_COLOR = {
    PathKind.PHYSICAL: plotting.PHYSICAL_COLOR,
    PathKind.CYBER: plotting.CYBER_COLOR,
    PathKind.MIXED: "#7b3fa0",
}


def main() -> None:
    plotting.use_style()
    m = navigation_case_study()
    q = exact_probability(m)
    ranked = most_likely(m)
    total_rare = math.fsum(c.probability for c in ranked)
    cut_table = table(
        [
            "rank",
            "minimal cut set",
            "kind",
            "P(all events)",
            "share of Σ",
            "attacker cost",
            "effort −ln P",
        ],
        [
            [
                i + 1,
                c.label(),
                str(c.kind),
                c.probability,
                c.probability / total_rare,
                c.attacker_cost if c.n_cyber else "—",
                c.effort,
            ]
            for i, c in enumerate(ranked)
        ],
    )
    by_kind = {k: math.fsum(c.probability for c in ranked if c.kind is k) for k in PathKind}
    kind_table = table(
        ["kind", "cut sets", "Σ P", "share"],
        [
            [str(k), sum(c.kind is k for c in ranked), by_kind[k], by_kind[k] / total_rare]
            for k in PathKind
        ],
    )
    rare = (
        f"Rare-event check: Σ P over cut sets = {total_rare:.6e} versus exact "
        f"P(TOP) = {q:.6e} (the sum is an upper bound; difference {total_rare - q:.2e}).\n"
    )
    attacks = table(
        ["attack (cyber-only cut set)", "attacker cost (weeks)", "P(success in window)"],
        [[c.label(), c.attacker_cost, c.probability] for c in cheapest_attacks(m)],
    )
    cost_note = (
        f"Exact minimum attacker cost: {min_attacker_cost(m):g} weeks "
        f"(bottom-up min-cost domain: {evaluate(m, MIN_COST)[m.top]:g}).\n"
    )
    front = table(
        ["scenario on the front", "kind", "attacker cost", "P(physical preconditions)"],
        [
            [c.label(), str(c.kind), c.attacker_cost, c.physical_probability]
            for c in opportunistic_front(m)
        ],
    )
    imp = importance_measures(m)
    imp_table = table(
        ["event", "origin", "q", "Birnbaum", "criticality", "Fussell–Vesely", "RAW", "RRW"],
        [
            [
                r.event,
                str(r.origin),
                r.probability,
                r.birnbaum,
                r.criticality,
                r.fussell_vesely,
                r.raw,
                r.rrw,
            ]
            for r in imp
        ],
    )
    eng_out = sorted(
        (r for r in imp if r.origin is Origin.CYBER), key=lambda r: (r.q_without, r.event)
    )
    eng_table = table(
        ["cyber step engineered out", "P(TOP) after", "risk reduction", "min attacker cost after"],
        [
            [
                r.event,
                r.q_without,
                1 - r.q_without / q,
                min_attacker_cost(m.with_event(_impossible(m, r.event))),
            ]
            for r in eng_out
        ],
    )
    path = write_result(
        "critical_path",
        "Phase 4 · Critical paths and importance",
        [
            ("All minimal cut sets, most likely first", cut_table + "\n" + rare),
            ("Risk by kind of path", kind_table),
            ("Cheapest attacker-controlled paths", attacks + "\n" + cost_note),
            ("Opportunistic front: attacker cost vs physical preconditions", front),
            ("Importance measures (sorted by Fussell–Vesely)", imp_table),
            ("Engineering out one cyber step", eng_table),
        ],
    )

    # Figure 1: the three lowest-effort paths of each kind, highlighted on the model.
    best = {
        PathKind.PHYSICAL: next(c for c in ranked if c.kind is PathKind.PHYSICAL),
        PathKind.MIXED: next(c for c in ranked if c.kind is PathKind.MIXED),
        PathKind.CYBER: cheapest_attacks(m, 1)[0],
    }
    fig, axes = plt.subplots(1, 3, figsize=(24, 7.5))
    titles = {
        PathKind.PHYSICAL: "Most likely physical path",
        PathKind.MIXED: "Most likely mixed path",
        PathKind.CYBER: "Cheapest attacker-controlled path",
    }
    for ax, (kind, c) in zip(axes, best.items(), strict=True):
        plotting.draw_model(
            m, ax=ax, highlight=activated(m, c.events), title=f"{titles[kind]}: {c.label()}"
        )
    fig.tight_layout()
    fig.savefig(FIGURES / "critical_paths.png")
    plt.close(fig)

    # Figure 2: every cut set on attacker cost vs probability of physical preconditions.
    fig, ax = plt.subplots(figsize=(7, 4.2))
    points: dict[tuple[float, float], list[str]] = {}
    for c in describe(m):
        ax.scatter(
            c.attacker_cost, c.physical_probability, color=KIND_COLOR[c.kind], s=40, zorder=3
        )
        points.setdefault((c.attacker_cost, c.physical_probability), []).append(_short(c.label()))
    for (x, y), labels in points.items():
        cyber_row = y == 1.0
        ax.annotate(
            "; ".join(sorted(labels)),
            (x, y),
            fontsize=6.5,
            xytext=(3, 6) if cyber_row else (5, 2),
            textcoords="offset points",
            rotation=40 if cyber_row else 0,
        )
    f = opportunistic_front(m)
    ax.step(
        [c.attacker_cost for c in f],
        [c.physical_probability for c in f],
        where="post",
        color="#999999",
        ls="--",
        label="Pareto front",
    )
    for k, color in KIND_COLOR.items():
        ax.scatter([], [], color=color, label=f"{k} path")
    ax.set_yscale("log")
    ax.set_xlabel("attacker cost (analyst-weeks)")
    ax.set_ylabel("P(physical preconditions present)")
    ax.set_title("Each path: what it costs the attacker, what it needs from chance", pad=80)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.savefig(FIGURES / "critical_opportunistic_front.png")
    plt.close(fig)

    # Figure 3: Fussell–Vesely importance by origin.
    fig, ax = plt.subplots(figsize=(7, 4.5))
    shown = [r for r in imp if r.fussell_vesely > 1e-4]
    ax.barh(
        [r.event for r in shown][::-1],
        [r.fussell_vesely for r in shown][::-1],
        color=[
            plotting.CYBER_COLOR if r.origin is Origin.CYBER else plotting.PHYSICAL_COLOR
            for r in shown
        ][::-1],
    )
    ax.set_xlabel("Fussell–Vesely importance (share of risk involving the event)")
    ax.set_title("Which events the risk runs through")
    fig.savefig(FIGURES / "critical_importance.png")
    plt.close(fig)
    print(f"wrote {path}")


SHORT = {
    "compromise_maintenance_laptop": "laptop",
    "supply_chain_implant": "implant",
    "inject_false_nav_messages": "inject",
    "defeat_load_verification": "verification",
    "malicious_program_download": "download",
    "integrity_monitor_miss": "monitor miss",
}


def _short(label: str) -> str:
    for long, short in SHORT.items():
        label = label.replace(long, short)
    return label


def _impossible(m: UnifiedModel, name: str) -> BasicEvent:
    """The cyber step made impossible: engineered out of the design."""
    return replace(m.events[name], probability=0.0, cost=math.inf)


if __name__ == "__main__":
    main()
