"""Phase 3: validate probability propagation and quantify the case study.

1. Classical reductions: all-physical models against closed-form RBD results.
2. The case study by four methods: exact, enumeration, Monte Carlo, naive bottom-up.
3. Origin views: physical-only, cyber-only, and the full model.
4. When the naive (tree) formulas go wrong on a DAG, and by how much.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from cpsrbd import plotting
from cpsrbd.consequence_driven_analysis import CONSEQUENCE, navigation_case_study
from cpsrbd.probability_likelihood_propagation import (
    bottom_up_probability,
    enumerate_probability,
    exact_probability,
    monte_carlo_probability,
    origin_overrides,
)
from cpsrbd.rbd import Block, KofN, Parallel, Series, bridge, reliability, to_unified
from cpsrbd.unified_graph_model import Origin

from common import FIGURES, table, write_result

MC_SAMPLES = 2_000_000
SEED = 2026


def classical_reductions() -> str:
    R = [0.9, 0.8, 0.95, 0.7, 0.85]
    b = [Block(f"b{i}", r) for i, r in enumerate(R)]
    cases = [
        ("series of 5", Series(tuple(b))),
        ("parallel of 5", Parallel(tuple(b))),
        ("2-out-of-3", KofN(2, tuple(b[:3]))),
        ("3-out-of-5", KofN(3, tuple(b))),
        ("bridge, R = 0.9", bridge([0.9] * 5)),
        ("bridge, distinct R", bridge(R)),
        ("series of (2 ∥ 3) and bridge", Series((Parallel((b[1], b[2])), bridge(R, "br")))),
    ]
    rows = []
    for name, rbd in cases:
        m = to_unified(rbd)
        closed = 1 - reliability(rbd) if name != "series of (2 ∥ 3) and bridge" else None
        exact = exact_probability(m)
        enum = enumerate_probability(m)
        ref = closed if closed is not None else enum
        rows.append(
            [
                name,
                "closed form" if closed is not None else "enumeration",
                ref,
                exact,
                abs(exact - ref),
                bottom_up_probability(m),
                len(m.shared_events()),
            ]
        )
    return table(
        [
            "structure",
            "reference",
            "1 − R (reference)",
            "exact (unified)",
            "abs. error",
            "naive bottom-up",
            "shared events",
        ],
        rows,
    )


def case_study() -> tuple[str, str, str, dict[str, float]]:
    m = navigation_case_study()
    exact = exact_probability(m)
    enum = enumerate_probability(m)
    naive = bottom_up_probability(m)
    mc = monte_carlo_probability(m, samples=MC_SAMPLES, seed=SEED)
    methods = table(
        ["method", "P(consequence)", "note"],
        [
            ["exact (Shannon on 4 shared events)", exact, "16 bottom-up passes"],
            ["enumeration", enum, f"|exact − enumeration| = {abs(exact - enum):.1e}"],
            [
                "Monte Carlo",
                mc.estimate,
                f"95 % CI [{mc.low:.4e}, {mc.high:.4e}], {MC_SAMPLES:,} samples, seed {SEED}",
            ],
            ["naive bottom-up", naive, f"relative error {(naive - exact) / exact:+.2%}"],
        ],
    )
    physical = exact_probability(m, origin_overrides(m, Origin.PHYSICAL))
    cyber = exact_probability(m, origin_overrides(m, Origin.CYBER))
    union = 1 - (1 - physical) * (1 - cyber)
    views = table(
        ["view", "P(consequence)", "share of the full model"],
        [
            ["physical failures only (classical reliability)", physical, physical / exact],
            ["cyber steps only (classical attack tree)", cyber, cyber / exact],
            ["both analysed separately, then combined", union, union / exact],
            ["unified model", exact, 1.0],
        ],
    )
    branches = []
    for gate in reversed(m.bottom_up()):
        if gate in m.gates and gate != m.top:
            sub = m.rooted_at(gate)
            branches.append(
                [
                    gate,
                    exact_probability(sub),
                    exact_probability(sub, origin_overrides(sub, Origin.PHYSICAL)),
                    exact_probability(sub, origin_overrides(sub, Origin.CYBER)),
                ]
            )
    branch_table = table(["branch", "P (unified)", "P (physical only)", "P (cyber only)"], branches)
    numbers = {"exact": exact, "physical": physical, "cyber": cyber, "union": union}
    return methods, views, branch_table, numbers


def views_figure(numbers: dict[str, float]) -> None:
    labels = ["physical only", "cyber only", "separate analyses\ncombined", "unified model"]
    values = [numbers["physical"], numbers["cyber"], numbers["union"], numbers["exact"]]
    colors = [plotting.PHYSICAL_COLOR, plotting.CYBER_COLOR, "#888888", "#333333"]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    bars = ax.bar(labels, values, color=colors)
    for bar, v in zip(bars, values, strict=True):
        ax.text(bar.get_x() + bar.get_width() / 2, v, f"{v:.2e}", ha="center", va="bottom")
    ax.set_ylabel("P(consequence) per mission")
    ax.set_title("What each view of the system sees")
    ax.grid(axis="x", visible=False)
    fig.savefig(FIGURES / "propagation_views.png")
    plt.close(fig)


def naive_error_figure() -> str:
    """Relative error of the tree formulas on DAGs as failure probabilities grow."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    # (a) the bridge with identical components
    q = np.linspace(0.01, 0.6, 60)
    errs = []
    for qi in q:
        m = to_unified(bridge([1 - qi] * 5))
        exact = exact_probability(m)
        errs.append((bottom_up_probability(m) - exact) / exact)
    axes[0].plot(q, 100 * np.array(errs), color="#333333")
    axes[0].set_xlabel("component failure probability q")
    axes[0].set_ylabel("naive − exact (% of exact)")
    axes[0].set_title("(a) Bridge network")
    # (b) the case study as the window grows (physical) and the cyber band widens
    hours = np.geomspace(1, 10_000, 40)
    rows = []
    for top_band, style in ((1e-1, "-"), (3e-1, "--"), (9e-1, ":")):
        errs_b = []
        for h in hours:
            m = navigation_case_study(mission_hours=float(h), band=(1e-4, top_band))
            exact = exact_probability(m)
            errs_b.append((bottom_up_probability(m) - exact) / exact)
        axes[1].semilogx(
            hours,
            100 * np.array(errs_b),
            style,
            color="#333333",
            label=f"cyber band up to {top_band:g}",
        )
        rows.append([top_band, errs_b[0], errs_b[np.argmin(abs(hours - 10))], errs_b[-1]])
    axes[1].set_xlabel("analysis window (h)")
    axes[1].set_title("(b) Case study")
    axes[1].legend(frameon=False, fontsize=8)
    fig.suptitle("Tree formulas on a DAG: the error from treating shared events as independent")
    fig.tight_layout()
    fig.savefig(FIGURES / "propagation_naive_error.png")
    plt.close(fig)
    bridge_rows = [[f"{qi:.2f}", e] for qi, e in zip(q[::12], errs[::12], strict=True)]
    return (
        table(["bridge q", "relative error"], bridge_rows)
        + "\n"
        + table(["cyber band top", "error at 1 h", "error at 10 h", "error at 10 000 h"], rows)
    )


def monte_carlo_figure(exact: float) -> None:
    m = navigation_case_study()
    ns = np.geomspace(1e3, MC_SAMPLES, 12).astype(int)
    est, lo, hi = [], [], []
    for n in ns:
        r = monte_carlo_probability(m, samples=int(n), seed=SEED)
        est.append(r.estimate)
        lo.append(r.low)
        hi.append(r.high)
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.fill_between(ns, lo, hi, color="#bbbbbb", label="95 % Wilson interval")
    ax.semilogx(ns, est, "o-", color="#333333", ms=3, label="Monte Carlo estimate")
    ax.axhline(exact, color=plotting.CYBER_COLOR, label=f"exact = {exact:.4e}")
    ax.set_xlabel("samples")
    ax.set_ylabel("P(consequence)")
    ax.set_title("Monte Carlo converges to the exact value")
    ax.legend(frameon=False, fontsize=8)
    fig.savefig(FIGURES / "propagation_monte_carlo.png")
    plt.close(fig)


def main() -> None:
    plotting.use_style()
    reductions = classical_reductions()
    methods, views, branches, numbers = case_study()
    views_figure(numbers)
    naive = naive_error_figure()
    monte_carlo_figure(numbers["exact"])
    path = write_result(
        "propagation",
        "Phase 3 · Probability propagation",
        [
            ("Classical reductions (all-physical models)", reductions),
            (f"Case study: P({CONSEQUENCE.name}) per mission", methods),
            ("Origin views", views),
            ("Every branch", branches),
            ("Naive (tree) formulas on DAGs", naive),
        ],
    )
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
