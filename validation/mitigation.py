"""Phase 5: physical vs cyber mitigation trade-offs in the case study, and their robustness."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

from cpsrbd import plotting
from cpsrbd.consequence_driven_analysis import navigation_case_study
from cpsrbd.mitigation_tradeoff_analysis import (
    Portfolio,
    assess,
    best_within_budget,
    case_study_mitigations,
    pareto_front,
    portfolios,
    tornado,
    uncertainty_samples,
)
from cpsrbd.probability_likelihood_propagation import exact_probability
from cpsrbd.unified_graph_model import Origin

from common import FIGURES, table, write_result

BUDGETS = (100, 200, 300, 500, 800)
SAMPLES = 500
SEED = 2026
BANDS = ((1e-5, 1e-2), (1e-4, 1e-1), (1e-3, 3e-1))
CATEGORY_COLOR = {
    "physical": plotting.PHYSICAL_COLOR,
    "cyber": plotting.CYBER_COLOR,
    "engineer-out": "#7b3fa0",
}


def main() -> None:
    plotting.use_style()
    model = navigation_case_study()
    options = case_study_mitigations()
    category = {o.name: str(o.category) for o in options}

    catalogue = table(
        ["option", "category", "investment", "effect on the model"],
        [[o.name, str(o.category), o.investment, o.description] for o in options],
    )
    singles = sorted(assess(model, options), key=lambda a: -a.reduction_per_investment)
    single_table = table(
        [
            "option",
            "category",
            "investment",
            "P(TOP) after",
            "risk reduction",
            "reduction per 100 units",
            "cheapest attack after (weeks)",
        ],
        [
            [
                a.name,
                category[a.name],
                a.investment,
                a.q_after,
                a.risk_reduction,
                100 * a.reduction_per_investment,
                a.cost_after,
            ]
            for a in singles
        ],
    )

    every = portfolios(model, options)
    risk_front = pareto_front(every, "risk")
    effort_front = pareto_front(every, "effort")

    def names(p: Portfolio) -> str:
        return ", ".join(p.names) or "(none)"

    front_table = table(
        ["investment", "P(TOP)", "cheapest attack", "physical share", "portfolio"],
        [[p.investment, p.q, p.attacker_cost, p.physical_share, names(p)] for p in risk_front],
    )
    effort_table = table(
        ["investment", "cheapest attack", "P(TOP)", "portfolio"],
        [[p.investment, p.attacker_cost, p.q, names(p)] for p in effort_front],
    )
    budget_rows = []
    for b in BUDGETS:
        r = best_within_budget(every, b, "risk")
        e = best_within_budget(every, b, "effort")
        budget_rows.append([b, names(r), r.q, r.attacker_cost, names(e), e.q, e.attacker_cost])
    budget_table = table(
        [
            "budget",
            "best for risk",
            "P(TOP)",
            "attack cost",
            "best for attacker effort",
            "P(TOP)",
            "attack cost",
        ],
        budget_rows,
    )

    bars = tornado(model, factor=3.0)
    tornado_table = table(
        ["event", "origin", "P(TOP), q ÷ 3", "P(TOP), q × 3", "swing"],
        [[b.event, str(b.origin), b.q_low, b.q_high, b.swing] for b in bars],
    )

    # Uncertainty: lognormal error factors 3 (physical) and 10 (cyber), common random numbers.
    samples = uncertainty_samples(model, options, samples=SAMPLES, seed=SEED)
    per_cost = np.array([samples[o.name] / o.investment for o in options])
    best_idx = np.argmax(per_cost, axis=0)
    unc_rows = []
    for i, o in enumerate(options):
        red = samples[o.name]
        unc_rows.append(
            [
                o.name,
                category[o.name],
                float(np.median(red)),
                float(np.quantile(red, 0.05)),
                float(np.quantile(red, 0.95)),
                float(np.mean(best_idx == i)),
            ]
        )
    unc_rows.sort(key=lambda r: -r[5])
    base = samples["baseline"]
    unc_table = table(
        [
            "option",
            "category",
            "median reduction",
            "5th pct",
            "95th pct",
            "P(best reduction per unit invested)",
        ],
        unc_rows,
    ) + (
        f"\nBaseline P(TOP) over {SAMPLES} draws (seed {SEED}): median {np.median(base):.3e}, "
        f"90 % interval [{np.quantile(base, 0.05):.3e}, {np.quantile(base, 0.95):.3e}].\n"
    )

    band_rows = []
    for band in BANDS:
        m = navigation_case_study(band=band)
        ranked = sorted(assess(m, options), key=lambda a: -a.reduction_per_investment)
        band_rows.append(
            [
                f"{band[0]:g} – {band[1]:g}",
                ranked[0].q_before,
                ranked[0].name,
                ranked[1].name,
                ranked[2].name,
            ]
        )
    band_table = table(
        ["cyber likelihood band", "P(TOP)", "best per unit invested", "2nd", "3rd"], band_rows
    )

    path = write_result(
        "mitigation",
        "Phase 5 · Mitigation trade-offs",
        [
            ("Candidate mitigations (investments are illustrative units)", catalogue),
            ("Each option alone, best risk reduction per unit invested first", single_table),
            ("Pareto front: investment vs risk (all 256 portfolios)", front_table),
            ("Pareto front: investment vs attacker effort", effort_table),
            ("Best portfolio within a budget", budget_table),
            ("Tornado: one probability at a time, divided and multiplied by 3", tornado_table),
            ("Uncertainty: lognormal inputs (EF 3 physical, EF 10 cyber)", unc_table),
            ("Changing the cyber likelihood band", band_table),
        ],
    )

    # Figure 1: all portfolios, risk and effort.
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    inv = np.array([p.investment for p in every])
    share = np.array([p.physical_share for p in every])
    sc = axes[0].scatter(
        inv, [p.q for p in every], c=share, cmap="coolwarm_r", s=14, vmin=0, vmax=1
    )
    axes[0].step(
        [p.investment for p in risk_front],
        [p.q for p in risk_front],
        where="post",
        color="#333333",
        lw=1.2,
        label="Pareto front",
    )
    axes[0].set_yscale("log")
    axes[0].set_xlabel("investment (units)")
    axes[0].set_ylabel("P(consequence) per mission")
    axes[0].set_title("(a) Risk")
    axes[0].legend(frameon=False, fontsize=8)
    costs = np.array([p.attacker_cost for p in every])
    finite = np.where(np.isinf(costs), np.nan, costs)
    axes[1].scatter(inv, finite, c=share, cmap="coolwarm_r", s=14, vmin=0, vmax=1)
    axes[1].step(
        [p.investment for p in effort_front],
        [p.attacker_cost for p in effort_front],
        where="post",
        color="#333333",
        lw=1.2,
        label="Pareto front",
    )
    axes[1].set_xlabel("investment (units)")
    axes[1].set_ylabel("cheapest attacker-controlled path (weeks)")
    axes[1].set_title("(b) Attacker effort")
    axes[1].legend(frameon=False, fontsize=8)
    cbar = fig.colorbar(sc, ax=axes, shrink=0.85)
    cbar.set_label("share of the investment that is physical")
    fig.suptitle("All 256 portfolios of the 8 options")
    fig.savefig(FIGURES / "mitigation_portfolios.png")
    plt.close(fig)

    # Figure 2: tornado.
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    shown = bars[:10][::-1]
    q0 = exact_probability(model)
    for i, b in enumerate(shown):
        color = plotting.CYBER_COLOR if b.origin is Origin.CYBER else plotting.PHYSICAL_COLOR
        ax.barh(i, b.q_high - q0, left=q0, color=color)
        ax.barh(i, b.q_low - q0, left=q0, color=color, alpha=0.45)
    ax.axvline(q0, color="#333333", lw=1)
    ax.set_yticks(range(len(shown)), [b.event for b in shown])
    ax.set_xlabel("P(consequence) when one probability is ÷ 3 (light) or × 3 (dark)")
    ax.set_title("Sensitivity of the consequence to each input")
    fig.savefig(FIGURES / "mitigation_tornado.png")
    plt.close(fig)

    # Figure 3: uncertainty of each option's risk reduction.
    fig, ax = plt.subplots(figsize=(8, 4.4))
    order = sorted(options, key=lambda o: -float(np.median(samples[o.name])))
    data = [100 * samples[o.name] for o in order]
    parts = ax.boxplot(
        data,
        orientation="horizontal",
        whis=(5, 95),
        showfliers=False,
        patch_artist=True,
        medianprops={"color": "black"},
    )
    for patch, o in zip(parts["boxes"], order, strict=True):
        patch.set_facecolor(CATEGORY_COLOR[str(o.category)])
        patch.set_alpha(0.7)
    ax.set_yticks(range(1, len(order) + 1), [o.name for o in order])
    ax.invert_yaxis()
    ax.set_xlabel("risk reduction (%) — box: quartiles, whiskers: 5th–95th percentile")
    ax.set_title(f"How sure are we? {SAMPLES} draws of every input")
    handles = [Patch(color=c, alpha=0.7, label=k) for k, c in CATEGORY_COLOR.items()]
    ax.legend(handles=handles, frameon=False, fontsize=8, loc="lower right")
    fig.savefig(FIGURES / "mitigation_uncertainty.png")
    plt.close(fig)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
