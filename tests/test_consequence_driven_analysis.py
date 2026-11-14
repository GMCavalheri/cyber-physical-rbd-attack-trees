import math
from pathlib import Path

import matplotlib
import pytest

from cpsrbd import plotting
from cpsrbd.consequence_driven_analysis import (
    CONSEQUENCE,
    BranchKind,
    Consequence,
    ConsequenceBuilder,
    branch_kinds,
    branch_origins,
    combined_score,
    events_from_parameters,
    likelihood_from_scores,
    load_parameters,
    navigation_case_study,
    paths_to,
)
from cpsrbd.unified_graph_model import ModelError, Origin, physical_event

matplotlib.use("Agg")

# ATT&CK for ICS techniques used in the case study, with their names as listed on
# https://attack.mitre.org/techniques/ics/ (checked 2026-11-14).
ATTACK_ICS = {
    "T0814": "Denial of Service",
    "T0843": "Program Download",
    "T0847": "Replication Through Removable Media",
    "T0849": "Masquerading",
    "T0856": "Spoof Reporting Message",
    "T0862": "Supply Chain Compromise",
}


# ------------------------------------------------------------------ scoring


def test_score_range_and_band_endpoints() -> None:
    assert combined_score(5, 1) == 2  # hardest, least exposed
    assert combined_score(1, 5) == 10  # easiest, most exposed
    assert likelihood_from_scores(5, 1) == pytest.approx(1e-4, rel=1e-12)
    assert likelihood_from_scores(1, 5) == pytest.approx(1e-1, rel=1e-12)
    # middle of the scale is the geometric mean of the band: 10^-2.5
    assert likelihood_from_scores(3, 3) == pytest.approx(10**-2.5, rel=1e-12)


def test_scoring_is_monotone() -> None:
    for cap in range(1, 6):
        ps = [likelihood_from_scores(cap, opp) for opp in range(1, 6)]
        assert ps == sorted(ps)
    for opp in range(1, 6):
        ps = [likelihood_from_scores(cap, opp) for cap in range(1, 6)]
        assert ps == sorted(ps, reverse=True)


@pytest.mark.parametrize(("cap", "opp"), [(0, 3), (3, 6)])
def test_scores_off_the_scale_are_rejected(cap: int, opp: int) -> None:
    with pytest.raises(ValueError):
        combined_score(cap, opp)


def test_band_must_be_ordered() -> None:
    with pytest.raises(ValueError):
        likelihood_from_scores(3, 3, band=(0.1, 0.01))
    assert likelihood_from_scores(3, 3, band=(1e-3, 1e-3)) == pytest.approx(1e-3)


# ------------------------------------------------------------------ builder


def test_builder_requires_every_cause_to_be_developed() -> None:
    b = ConsequenceBuilder(Consequence("top", "bad thing"))
    b.any_of("top", "a", "sub")
    b.events([physical_event("a", probability=0.1)])
    assert b.undeveloped() == ["sub"]
    with pytest.raises(ModelError, match="undeveloped"):
        b.build()
    b.all_of("sub", "x", "y")
    b.events([physical_event("x", probability=0.1), physical_event("y", probability=0.2)])
    m = b.build()
    assert m.top == "top" and m.description == "bad thing"
    assert m.structure_function({"a": False, "x": True, "y": True})


def test_builder_is_top_down() -> None:
    b = ConsequenceBuilder(Consequence("top", ""))
    with pytest.raises(ModelError, match="before any node refers"):
        b.any_of("orphan", "a")
    b.at_least("top", 2, "a", "b", "c")
    b.events(physical_event(n, probability=0.1) for n in "abc")
    assert b.build().gates["top"].k == 2


# ------------------------------------------------------------------ parameters


def test_packaged_parameters_load_and_state_their_basis() -> None:
    rows = load_parameters()
    assert len(rows) == 15
    assert all(r.basis for r in rows)
    cyber = [r for r in rows if r.origin == "cyber"]
    assert all("effect" in r.basis or "assumption" in r.basis for r in cyber)


def test_techniques_are_real_attack_for_ics_ids() -> None:
    used = {r.technique for r in load_parameters() if r.technique}
    assert used <= set(ATTACK_ICS)


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("x,physical,d,1e-4,0.1,,,,,assumed", "not both"),
        ("x,physical,d,,,,,,,assumed", "not both"),
        ("x,cyber,d,,,3,,4,,assumed", "scores"),
        ("x,martian,d,,0.1,,,,,assumed", "unknown origin"),
        ("x,physical,d,,0.1,,,,,", "basis"),
    ],
)
def test_bad_parameter_rows(tmp_path: Path, row: str, message: str) -> None:
    header = (
        "name,origin,description,failure_rate_per_hour,probability,capability_required,"
        "opportunity,cost_weeks,technique,basis"
    )
    path = tmp_path / "p.csv"
    path.write_text(f"{header}\n{row}\n")
    with pytest.raises(ValueError, match=message):
        load_parameters(path)


def test_events_follow_window_and_band() -> None:
    rows = load_parameters()
    short = {e.name: e for e in events_from_parameters(rows, mission_hours=1.0)}
    long = {e.name: e for e in events_from_parameters(rows, mission_hours=100.0)}
    # p = 1 - exp(-lambda t) with lambda = 2e-4 /h
    assert short["egi_1_hw"].probability == pytest.approx(-math.expm1(-2e-4), rel=1e-14)
    assert long["egi_1_hw"].probability == pytest.approx(-math.expm1(-2e-2), rel=1e-14)
    assert short["integrity_monitor_miss"].probability == 0.1  # fixed per-episode value
    wide = {e.name: e for e in events_from_parameters(rows, band=(1e-6, 1e-1))}
    assert wide["supply_chain_implant"].probability < short["supply_chain_implant"].probability
    assert short["flood_bus"].cost == 2.0
    assert short["flood_bus"].attributes["technique"] == "T0814"


# ------------------------------------------------------------------ the case study


def test_case_study_structure() -> None:
    m = navigation_case_study()
    assert m.top == CONSEQUENCE.name
    assert len(m.basic_events()) == 15
    assert len(m.gates) == 15
    assert m.origins() == {Origin.PHYSICAL, Origin.CYBER}
    # shared physical (power buses) and shared cyber (bus access) dependencies make it a DAG
    assert m.shared_events() == [
        "compromise_maintenance_laptop",
        "power_bus_1",
        "power_bus_2",
        "supply_chain_implant",
    ]
    assert m.path_counts()["bus_access_gained"] == 2


def test_case_study_boolean_spot_checks() -> None:
    m = navigation_case_study()
    none = {e.name: False for e in m.basic_events()}
    assert not m.structure_function(none)
    # one navigation unit alone is tolerated (redundancy) ...
    assert not m.structure_function(none | {"egi_1_hw": True})
    # ... but losing power bus 1 and unit 2 removes both sources
    assert m.structure_function(none | {"power_bus_1": True, "egi_2_hw": True})
    # a GNSS spoof alone is caught by the integrity cross-check ...
    assert not m.structure_function(none | {"gnss_spoof": True})
    # ... unless the cross-check misses it: a mixed physical + cyber path
    assert m.structure_function(none | {"gnss_spoof": True, "integrity_monitor_miss": True})
    # bus access and message injection, a purely cyber path
    assert m.structure_function(
        none | {"compromise_maintenance_laptop": True, "inject_false_nav_messages": True}
    )


def test_branch_classification() -> None:
    m = navigation_case_study()
    kinds = branch_kinds(m)
    assert kinds["both_nav_sources_lost"] is BranchKind.PHYSICAL
    assert kinds["malicious_load"] is BranchKind.CYBER
    assert kinds["spoofed_gnss_accepted"] is BranchKind.MIXED
    assert kinds[m.top] is BranchKind.MIXED
    assert branch_origins(m)["flood_bus"] == {Origin.CYBER}


def test_paths_walk_back_from_the_consequence() -> None:
    m = navigation_case_study()
    paths = paths_to(m, "compromise_maintenance_laptop")
    assert len(paths) == m.path_counts()["compromise_maintenance_laptop"] == 3
    assert all(p[0] == m.top and p[-1] == "compromise_maintenance_laptop" for p in paths)
    assert paths_to(m, m.top) == [[m.top]]
    with pytest.raises(ModelError):
        paths_to(m, "nope")


def test_drawing_places_every_node(tmp_path: Path) -> None:
    m = navigation_case_study()
    pos = plotting.layered_layout(m)
    assert set(pos) == set(m.reachable())
    assert pos[m.top][1] == 0.0
    # every edge points downward
    for parent in m.gates:
        for child in m.children(parent):
            assert pos[child][1] < pos[parent][1]
    plotting.use_style()
    fig = plotting.draw_model(m, highlight={m.top, "nav_data_unavailable"}, title="t")
    fig.savefig(tmp_path / "m.png")
    assert (tmp_path / "m.png").stat().st_size > 10_000
