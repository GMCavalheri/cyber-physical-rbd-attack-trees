"""Phase 2: build the case-study model, draw it, and tabulate its parameters and branches."""

from __future__ import annotations

from collections import Counter

from cpsrbd import plotting
from cpsrbd.consequence_driven_analysis import (
    CONSEQUENCE,
    MISSION_HOURS,
    branch_kinds,
    load_parameters,
    navigation_case_study,
)

from common import FIGURES, table, write_result


def main() -> None:
    model = navigation_case_study()
    plotting.use_style()
    fig = plotting.draw_model(model, title=f"Consequence: {CONSEQUENCE.statement}")
    fig.savefig(FIGURES / "case_study_model.png")

    rows = load_parameters()
    events = {e.name: e for e in model.basic_events()}
    params = table(
        [
            "event",
            "origin",
            "rate (/h)",
            "scores (cap, opp)",
            "P in window",
            "cost (weeks)",
            "ATT&CK for ICS",
            "basis",
        ],
        [
            [
                r.name,
                r.origin,
                r.failure_rate_per_hour if r.failure_rate_per_hour is not None else "—",
                f"{r.capability_required}, {r.opportunity}" if r.origin == "cyber" else "—",
                events[r.name].probability,
                events[r.name].cost,
                r.technique or "—",
                r.basis,
            ]
            for r in rows
        ],
    )
    kinds = branch_kinds(model)
    gates = table(
        ["gate", "type", "children", "can be triggered by"],
        [
            [g, str(model.gates[g].kind), ", ".join(model.children(g)), str(kinds[g])]
            for g in reversed(model.bottom_up())
            if g in model.gates
        ],
    )
    counts = Counter(str(k) for k in kinds.values())
    shared = table(
        ["shared event", "paths to the top event"],
        [[n, model.path_counts()[n]] for n in model.shared_events()],
    )
    summary = (
        f"- Consequence: *{CONSEQUENCE.statement}* (`{CONSEQUENCE.name}`)\n"
        f"- Analysis window: {MISSION_HOURS:g} h (one mission)\n"
        f"- {len(model.gates)} gates; {sum(e.origin == 'physical' for e in events.values())} "
        f"physical events; {sum(e.origin == 'cyber' for e in events.values())} cyber steps\n"
        f"- Gates by what can trigger them: "
        + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
        + "\n"
    )
    path = write_result(
        "case_study",
        "Phase 2 · The navigation case study",
        [
            ("Summary", summary),
            ("Basic events", params),
            ("Gates, top-down", gates),
            ("Shared events (why the model is a DAG)", shared),
        ],
    )
    print(f"wrote {path} and {FIGURES / 'case_study_model.png'}")


if __name__ == "__main__":
    main()
