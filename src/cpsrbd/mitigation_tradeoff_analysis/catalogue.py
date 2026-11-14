"""Candidate mitigations for the navigation case study (all values are assumptions).

Investments are in illustrative cost units (think k$ of design, hardware and qualification
effort); probability factors and added attacker costs are round, judgement-based values chosen
to be plausible and easy to vary. Every option is described by its *effect* on the model.
"""

from __future__ import annotations

from cpsrbd.consequence_driven_analysis.scoring import likelihood_from_scores
from cpsrbd.mitigation_tradeoff_analysis.mitigations import (
    AddRedundancy,
    Category,
    EngineerOut,
    Mitigation,
    ReduceProbability,
    RequireStep,
)
from cpsrbd.unified_graph_model import cyber_step


def case_study_mitigations() -> list[Mitigation]:
    return [
        AddRedundancy(
            "redundant_mission_computer",
            300.0,
            Category.PHYSICAL,
            events=("mc_hw",),
            beta=0.05,
            description="Second mission computer; 5 % of failures are common-cause",
        ),
        ReduceProbability(
            "stronger_integrity_monitor",
            150.0,
            Category.PHYSICAL,
            event="integrity_monitor_miss",
            factor=0.1,
            description="Tighter GNSS/inertial cross-check: misses 1 spoof in 100, not 1 in 10",
        ),
        AddRedundancy(
            "independent_nav_power",
            80.0,
            Category.PHYSICAL,
            events=("power_bus_1", "power_bus_2"),
            beta=0.1,
            description="Backup power feed for each navigation unit and the computer",
        ),
        ReduceProbability(
            "anti_spoof_gnss_antenna",
            250.0,
            Category.CYBER,
            event="gnss_spoof",
            factor=0.1,
            added_cost=8.0,
            description="Spoofing-resistant antenna/receiver: harder and costlier to spoof",
        ),
        ReduceProbability(
            "harden_maintenance_laptop",
            40.0,
            Category.CYBER,
            event="compromise_maintenance_laptop",
            factor=0.3,
            added_cost=4.0,
            description="Hardened, controlled maintenance laptop",
        ),
        RequireStep(
            "authenticate_bus_messages",
            200.0,
            Category.CYBER,
            target="inject_false_nav_messages",
            step=cyber_step(
                "defeat_message_authentication",
                probability=likelihood_from_scores(4, 2),
                cost=12.0,
                description="Forge authenticated navigation messages (effect level)",
                capability_required=4.0,
                opportunity=2.0,
            ),
            description="Navigation messages are authenticated; injection must defeat it",
        ),
        RequireStep(
            "bus_guardian",
            180.0,
            Category.CYBER,
            target="flood_bus",
            step=cyber_step(
                "defeat_bus_guardian",
                probability=likelihood_from_scores(4, 2),
                cost=10.0,
                description="Get past per-node transmit guardians (effect level)",
                capability_required=4.0,
                opportunity=2.0,
            ),
            description="Per-node bus guardians stop one node from flooding both channels",
        ),
        EngineerOut(
            "offline_software_loader",
            120.0,
            Category.ENGINEER_OUT,
            events=("compromise_maintenance_laptop",),
            description="Dedicated offline loader; no general-purpose laptop touches the bus",
        ),
    ]
