"""The synthetic case study: loss of trusted navigation data at a mission computer.

A generic, defense-representative platform (no real system is modelled) carries two embedded
GNSS/INS navigation units, each powered from its own electrical bus, that publish navigation
solutions on a dual-channel data bus to a mission computer fed from both power buses. A
maintenance laptop is used to load software onto the mission computer.

The consequence, stated CCE-style, is *"the mission computer loses trustworthy navigation data
during the mission"*: either no navigation data reaches it (loss of availability), or false
data reaches it and is accepted (loss of integrity). The model is developed top-down from that
statement in :func:`navigation_case_study`; ``docs/figures/case_study_model.png`` draws it.

All numbers come from ``data/case_study_parameters.csv`` and every row states its basis.
Physical rates are round, plausible assumptions; cyber likelihoods come from the illustrative
scoring in :mod:`cpsrbd.consequence_driven_analysis.scoring`. Cyber steps are described by
their *effect* on the system only (see ``docs/scope.md``).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from cpsrbd.consequence_driven_analysis.builder import Consequence, ConsequenceBuilder
from cpsrbd.consequence_driven_analysis.scoring import DEFAULT_BAND, likelihood_from_scores
from cpsrbd.unified_graph_model import BasicEvent, UnifiedModel, cyber_step, physical_event

MISSION_HOURS = 10.0
"""Analysis window: one mission (assumption)."""

CONSEQUENCE = Consequence(
    "loss_of_trusted_navigation",
    "The mission computer loses trustworthy navigation data during the mission",
)


@dataclass(frozen=True)
class Parameter:
    """One row of the parameter table."""

    name: str
    origin: str
    description: str
    failure_rate_per_hour: float | None
    probability: float | None
    capability_required: int | None
    opportunity: int | None
    cost_weeks: float | None
    technique: str
    basis: str


def _number(text: str) -> float | None:
    return float(text) if text.strip() else None


def _integer(text: str) -> int | None:
    return int(text) if text.strip() else None


def load_parameters(path: Path | None = None) -> list[Parameter]:
    """Read the parameter CSV (the packaged one by default) and check every row."""
    if path is None:
        text = resources.files("cpsrbd.data").joinpath("case_study_parameters.csv").read_text()
    else:
        text = path.read_text()
    rows = []
    for raw in csv.DictReader(text.splitlines()):
        row = Parameter(
            name=raw["name"],
            origin=raw["origin"],
            description=raw["description"],
            failure_rate_per_hour=_number(raw["failure_rate_per_hour"]),
            probability=_number(raw["probability"]),
            capability_required=_integer(raw["capability_required"]),
            opportunity=_integer(raw["opportunity"]),
            cost_weeks=_number(raw["cost_weeks"]),
            technique=raw["technique"].strip(),
            basis=raw["basis"].strip(),
        )
        if not row.basis:
            raise ValueError(f"{row.name}: every parameter must state its basis")
        if row.origin == "physical":
            if (row.failure_rate_per_hour is None) == (row.probability is None):
                raise ValueError(f"{row.name}: give a failure rate or a probability, not both")
        elif row.origin == "cyber":
            if row.capability_required is None or row.opportunity is None or row.cost_weeks is None:
                raise ValueError(f"{row.name}: cyber steps need both scores and a cost")
        else:
            raise ValueError(f"{row.name}: unknown origin {row.origin!r}")
        rows.append(row)
    return rows


def events_from_parameters(
    rows: list[Parameter],
    mission_hours: float = MISSION_HOURS,
    band: tuple[float, float] = DEFAULT_BAND,
) -> list[BasicEvent]:
    """Turn parameter rows into basic events for a given window and likelihood band."""
    events = []
    for row in rows:
        if row.origin == "physical":
            if row.failure_rate_per_hour is not None:
                events.append(
                    physical_event(
                        row.name,
                        failure_rate=row.failure_rate_per_hour,
                        exposure_time=mission_hours,
                        description=row.description,
                        source=row.basis,
                    )
                )
            else:
                assert row.probability is not None
                events.append(
                    physical_event(
                        row.name,
                        probability=row.probability,
                        description=row.description,
                        source=row.basis,
                    )
                )
        else:
            assert row.capability_required is not None and row.opportunity is not None
            assert row.cost_weeks is not None
            events.append(
                cyber_step(
                    row.name,
                    probability=likelihood_from_scores(
                        row.capability_required, row.opportunity, band
                    ),
                    cost=row.cost_weeks,
                    description=row.description,
                    technique=row.technique,
                    source=row.basis,
                    capability_required=float(row.capability_required),
                    opportunity=float(row.opportunity),
                )
            )
    return events


def navigation_case_study(
    mission_hours: float = MISSION_HOURS,
    band: tuple[float, float] = DEFAULT_BAND,
    parameters: Path | None = None,
) -> UnifiedModel:
    """Build the case-study model, consequence first."""
    events = events_from_parameters(load_parameters(parameters), mission_hours, band)
    b = ConsequenceBuilder(CONSEQUENCE)
    # The consequence: no navigation data, or false navigation data accepted.
    b.any_of(
        CONSEQUENCE.name,
        "nav_data_unavailable",
        "misleading_nav_accepted",
        description=CONSEQUENCE.statement,
    )
    # Availability: the function needs a source, a data path and the computer itself.
    b.any_of(
        "nav_data_unavailable",
        "both_nav_sources_lost",
        "data_path_lost",
        "mission_computer_lost",
        description="No navigation data reaches the mission computer",
    )
    b.all_of(
        "both_nav_sources_lost",
        "nav_unit_1_lost",
        "nav_unit_2_lost",
        description="Both navigation units are lost (1-out-of-2 redundancy)",
    )
    b.any_of("nav_unit_1_lost", "egi_1_hw", "power_bus_1", description="Unit 1 or its power")
    b.any_of("nav_unit_2_lost", "egi_2_hw", "power_bus_2", description="Unit 2 or its power")
    b.any_of(
        "data_path_lost",
        "both_bus_channels_failed",
        "bus_denied",
        description="The data bus no longer delivers navigation messages",
    )
    b.all_of("both_bus_channels_failed", "bus_ch_a", "bus_ch_b", description="Dual channel")
    b.all_of(
        "bus_denied",
        "bus_access_gained",
        "flood_bus",
        description="An adversary on the bus denies both channels",
    )
    b.any_of(
        "bus_access_gained",
        "compromise_maintenance_laptop",
        "supply_chain_implant",
        description="Adversary code runs on a bus-connected device",
    )
    b.any_of(
        "mission_computer_lost",
        "mc_hw",
        "mc_power_lost",
        "malicious_load",
        description="The mission computer stops processing navigation data",
    )
    b.all_of(
        "mc_power_lost",
        "power_bus_1",
        "power_bus_2",
        description="The computer is fed from both buses",
    )
    b.all_of(
        "malicious_load",
        "compromise_maintenance_laptop",
        "malicious_program_download",
        "defeat_load_verification",
        description="A modified software load disables navigation processing",
    )
    # Integrity: false data that the system accepts.
    b.any_of(
        "misleading_nav_accepted",
        "spoofed_gnss_accepted",
        "injected_nav_accepted",
        description="False navigation data reaches the computer and is accepted",
    )
    b.all_of(
        "spoofed_gnss_accepted",
        "gnss_spoof",
        "integrity_monitor_miss",
        description="A GNSS spoof that the integrity cross-check misses",
    )
    b.all_of(
        "injected_nav_accepted",
        "bus_access_gained",
        "inject_false_nav_messages",
        description="False navigation messages injected from a compromised bus device",
    )
    b.events(events)
    return b.build()
