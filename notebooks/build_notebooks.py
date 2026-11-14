"""Generate and execute the demo notebooks, one per lesson, from the cell sources below.

    uv run python notebooks/build_notebooks.py           # write and execute all notebooks
    uv run python notebooks/build_notebooks.py --check   # execute in memory only (CI)

Keeping the sources here, instead of hand-editing .ipynb JSON, makes the notebooks reviewable
in diffs. Every computation in them is exact or seeded, so a rebuild reproduces them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

HERE = Path(__file__).resolve().parent

SETUP = """\
import matplotlib.pyplot as plt

from cpsrbd import plotting

plotting.use_style()"""

Cell = tuple[str, str]

NOTEBOOKS: dict[str, list[Cell]] = {
    "01_two_languages.ipynb": [
        (
            "md",
            """\
# 1 · Two languages for one failure

An RBD in success logic, converted exactly into the unified failure-logic model. See
[Lesson 1](../docs/lessons/01-two-languages-for-one-failure.md).""",
        ),
        ("code", SETUP),
        (
            "code",
            """\
from cpsrbd.rbd import Block, KofN, Parallel, Series, bridge, reliability, to_unified, works

pumps = Parallel((Block("pump_1", 0.9), Block("pump_2", 0.9)), name="pumps")
train = Series((pumps, Block("valve", 0.99)), name="train")
print(f"R = {reliability(train):.4f}")
model = to_unified(train, top="train_fails")
model""",
        ),
        ("md", "Duality, checked in every one of the $2^3$ states:"),
        (
            "code",
            """\
import itertools

names = ["pump_1", "pump_2", "valve"]
for states in itertools.product((False, True), repeat=3):
    working = {n for n, s in zip(names, states) if s}
    failed = {n: n not in working for n in names}
    assert model.structure_function(failed) is (not works(train, working))
print("top event happens exactly when the RBD fails")""",
        ),
        ("md", "The bridge: not series-parallel, so its converted model shares every component."),
        (
            "code",
            """\
b = to_unified(bridge([0.9] * 5))
print(b, "shared:", b.shared_events())
fig = plotting.draw_model(b, title="Bridge network in failure logic")""",
        ),
    ],
    "02_consequence_first.ipynb": [
        (
            "md",
            """\
# 2 · Start from the consequence

The synthetic navigation case study, built top-down from its consequence. See
[Lesson 2](../docs/lessons/02-start-from-the-consequence.md) and [scope](../docs/scope.md).""",
        ),
        ("code", SETUP),
        (
            "code",
            """\
from cpsrbd.consequence_driven_analysis import (
    CONSEQUENCE,
    branch_kinds,
    likelihood_from_scores,
    navigation_case_study,
    paths_to,
)

model = navigation_case_study()
print(CONSEQUENCE.statement)
print(model)
fig = plotting.draw_model(model, title=CONSEQUENCE.statement)""",
        ),
        ("md", "The likelihood scale for cyber steps (an explicit assumption):"),
        (
            "code",
            """\
for cap in range(1, 6):
    print(f"capability {cap}:", "  ".join(f"{likelihood_from_scores(cap, opp):.1e}" for opp in range(1, 6)))""",
        ),
        ("md", "Basic events and what can trigger each gate:"),
        (
            "code",
            """\
for e in model.basic_events():
    print(f"{e.name:30s} {e.origin:8s} p = {e.probability:.2e}  cost = {e.cost}")
print()
for gate, kind in branch_kinds(model).items():
    print(f"{gate:28s} {kind}")""",
        ),
        (
            "code",
            """\
for path in paths_to(model, "compromise_maintenance_laptop"):
    print(" → ".join(path))""",
        ),
    ],
    "03_propagation.ipynb": [
        (
            "md",
            """\
# 3 · Propagating probability through one graph

Exact, enumerated, sampled and naive propagation, and what each partial view sees. See
[Lesson 3](../docs/lessons/03-propagating-probability-and-likelihood.md).""",
        ),
        ("code", SETUP),
        (
            "code",
            """\
from cpsrbd.consequence_driven_analysis import navigation_case_study
from cpsrbd.probability_likelihood_propagation import (
    bottom_up_probability,
    enumerate_probability,
    exact_probability,
    monte_carlo_probability,
    origin_decomposition,
)

model = navigation_case_study()
print(f"exact        {exact_probability(model):.6e}")
print(f"enumeration  {enumerate_probability(model):.6e}")
print(f"naive        {bottom_up_probability(model):.6e}")
mc = monte_carlo_probability(model, samples=500_000, seed=7)
print(f"Monte Carlo  {mc.estimate:.3e}  95 % CI [{mc.low:.3e}, {mc.high:.3e}]")""",
        ),
        ("md", "Where shared events sit under an AND, the tree formulas fail badly:"),
        (
            "code",
            """\
from cpsrbd.rbd import bridge, to_unified

for q in (0.01, 0.1, 0.3):
    m = to_unified(bridge([1 - q] * 5))
    exact, naive = exact_probability(m), bottom_up_probability(m)
    print(f"q = {q:4}: exact {exact:.4e}  naive {naive:.4e}  error {(naive - exact) / exact:+.0%}")""",
        ),
        ("md", "Each team's view, and the interaction gap between them:"),
        (
            "code",
            """\
d = origin_decomposition(model)
print(f"physical only  {d.physical:.3e}")
print(f"cyber only     {d.cyber:.3e}")
print(f"combined       {d.separate:.3e}")
print(f"unified        {d.full:.3e}")
print(f"gap            {d.gap:.3e}  ({d.gap_share:.0%} of the risk)")""",
        ),
    ],
    "04_critical_paths.ipynb": [
        (
            "md",
            """\
# 4 · The lowest-effort path

Minimal cut sets, three meanings of "lowest effort", importance, and engineering out. See
[Lesson 4](../docs/lessons/04-the-lowest-effort-path.md).""",
        ),
        ("code", SETUP),
        (
            "code",
            """\
from cpsrbd.consequence_driven_analysis import navigation_case_study
from cpsrbd.critical_path_identification import (
    activated,
    cheapest_attacks,
    importance_measures,
    min_attacker_cost,
    most_likely,
    opportunistic_front,
)

model = navigation_case_study()
for c in most_likely(model):
    print(f"{c.probability:.2e}  {c.kind:8s}  {c.label()}")""",
        ),
        (
            "code",
            """\
print("cheapest attack:", cheapest_attacks(model, 1)[0].label(), f"({min_attacker_cost(model):g} weeks)")
print("opportunistic front:")
for c in opportunistic_front(model):
    print(f"  cost {c.attacker_cost:4g}  P(physical preconditions) {c.physical_probability:.1e}  {c.label()}")""",
        ),
        (
            "code",
            """\
best = cheapest_attacks(model, 1)[0]
fig = plotting.draw_model(model, highlight=activated(model, best.events), title=f"Cheapest attack: {best.label()}")""",
        ),
        ("md", "Importance, and the risk left after engineering out each cyber step:"),
        (
            "code",
            """\
for r in importance_measures(model)[:8]:
    print(f"{r.event:30s} FV {r.fussell_vesely:.3f}  RAW {r.raw:7.1f}  Q without {r.q_without:.3e}")""",
        ),
    ],
    "05_mitigations.ipynb": [
        (
            "md",
            """\
# 5 · Physical and cyber mitigations in one currency

Each option alone, the two Pareto fronts, and one-at-a-time sensitivity. The 500-draw
uncertainty study is in `validation/mitigation.py`. See
[Lesson 5](../docs/lessons/05-comparing-mitigations.md).""",
        ),
        ("code", SETUP),
        (
            "code",
            """\
from cpsrbd.consequence_driven_analysis import navigation_case_study
from cpsrbd.mitigation_tradeoff_analysis import (
    assess,
    case_study_mitigations,
    pareto_front,
    portfolios,
    tornado,
)

model = navigation_case_study()
options = case_study_mitigations()
for a in sorted(assess(model, options), key=lambda a: -a.risk_reduction):
    print(f"{a.name:28s} invest {a.investment:4.0f}  risk -{a.risk_reduction:5.1%}  cheapest attack {a.cost_after:g}")""",
        ),
        (
            "code",
            """\
every = portfolios(model, options)
for objective in ("risk", "effort"):
    print(f"Pareto front ({objective}):")
    for p in pareto_front(every, objective)[:6]:
        print(f"  {p.investment:5.0f}  P {p.q:.2e}  attack {p.attacker_cost:g}  {', '.join(p.names) or '(none)'}")""",
        ),
        (
            "code",
            """\
fig, ax = plt.subplots(figsize=(7, 4))
ax.scatter([p.investment for p in every], [p.q for p in every], s=10, c=[p.physical_share for p in every], cmap="coolwarm_r")
front = pareto_front(every, "risk")
ax.step([p.investment for p in front], [p.q for p in front], where="post", color="black")
ax.set_yscale("log")
ax.set_xlabel("investment")
ax.set_ylabel("P(consequence)")
ax.set_title("256 portfolios, colour = physical share")""",
        ),
        (
            "code",
            """\
for b in tornado(model)[:6]:
    print(f"{b.event:30s} {b.q_low:.2e} .. {b.q_high:.2e}")""",
        ),
    ],
    "06_semantics.ipynb": [
        (
            "md",
            """\
# 6 · Formal semantics and the interaction gap

The all-cyber reduction against an independent attack-tree implementation, and the worked
interaction-gap example. See [Lesson 6](../docs/lessons/06-formal-semantics-and-what-is-new.md)
and [the formal semantics](../docs/formal-semantics.md).""",
        ),
        (
            "code",
            """\
from cpsrbd import attack_tree as at
from cpsrbd.critical_path_identification import min_attacker_cost, minimal_cut_sets
from cpsrbd.probability_likelihood_propagation import exact_probability, origin_decomposition

tree = at.Or("goal", (at.And("ab", (at.Step("a", 0.5, 2), at.Step("b", 0.4, 3))), at.Step("c", 0.1, 10)))
m = at.to_unified(tree)
print("scenarios ", sorted(sorted(s) for s in at.scenarios(tree)))
print("cut sets  ", sorted(sorted(s) for s in minimal_cut_sets(m)))
print("probability", at.probability(tree), exact_probability(m))
print("min cost   ", at.min_cost(tree), min_attacker_cost(m))""",
        ),
        (
            "md",
            "The worked example of the interaction gap, $(p_1 \\wedge c_1) \\vee p_2 \\vee c_2$:",
        ),
        (
            "code",
            """\
from cpsrbd.unified_graph_model import UnifiedModel, cyber_step, physical_event

g = UnifiedModel("top")
g.add_events([
    physical_event("p1", probability=0.1),
    cyber_step("c1", probability=0.2, cost=1),
    physical_event("p2", probability=0.01),
    cyber_step("c2", probability=0.05, cost=9),
])
g.and_("mixed", "p1", "c1").or_("top", "mixed", "p2", "c2").validate()
d = origin_decomposition(g)
print(f"separate views combined {d.separate:.5f}, unified {d.full:.5f}, gap {d.gap:.5f} ({d.gap_share:.0%})")""",
        ),
    ],
}


def build(name: str, cells: list[Cell]) -> nbformat.NotebookNode:
    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {
        "name": "python3",
        "display_name": "Python 3",
        "language": "python",
    }
    nb.cells = [
        nbformat.v4.new_markdown_cell(src) if kind == "md" else nbformat.v4.new_code_cell(src)
        for kind, src in cells
    ]
    for i, cell in enumerate(nb.cells):
        cell["id"] = f"{Path(name).stem}-{i}"
    NotebookClient(
        nb,
        timeout=600,
        kernel_name="python3",
        record_timing=False,  # no timestamps: rebuilds are byte-identical
        resources={"metadata": {"path": str(HERE)}},
    ).execute()
    return nb


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="execute without writing")
    ap.add_argument("names", nargs="*", help="notebooks to build (default: all)")
    args = ap.parse_args()
    for name in args.names or list(NOTEBOOKS):
        print(f"== {name}", flush=True)
        nb = build(name, NOTEBOOKS[name])
        if not args.check:
            nbformat.write(nb, HERE / name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
