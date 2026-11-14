# PLAN.md — CPS-02: Unified Reliability Block Diagram and Attack Tree Framework

## Overview
A systems-modeling project unifying two classical but historically separate analysis tools — the Reliability Block Diagram (RBD, from reliability engineering) and the Attack Tree (from cybersecurity risk analysis) — into a single graph-based model that represents both physical failure paths and cyber attack paths to a given system-level consequence, in the spirit of Idaho National Laboratory's Consequence-driven Cyber-Informed Engineering (CCE) methodology.

## Objective
Build a unified modeling framework where a single system diagram represents both the physical redundancy/failure structure (RBD-style) and the cyber attack paths that could produce equivalent consequences (attack-tree-style), allowing "top event" consequences (e.g., loss of a critical function) to be analyzed regardless of whether the root cause is physical failure or cyber attack.

## Why This Project
This is the direct technical embodiment of CCE's "think like the adversary, starting from consequence" philosophy applied through a reliability engineer's native tool (the RBD from the Avionics Electronics Reliability project) rather than a cybersecurity-only tool. Most attack tree analysis lives entirely within cybersecurity teams and never connects to the system reliability models that engineering teams already maintain — this project builds that missing connective tissue as working software, not just a conceptual diagram.

## Knowledge Covered
1. **Unified Graph Representation**: design a single graph data structure capable of representing both RBD-style series/parallel physical reliability blocks and attack-tree-style AND/OR attack goal decomposition, with each node tagged as physical or cyber in origin.
2. **Consequence-Driven Top-Event Definition**: following the CCE methodology, start from a defined critical consequence (e.g., "loss of navigation data to the control system") and work backward to enumerate both the physical failure paths and cyber attack paths that could produce it — this "consequence-first" framing is the project's core methodological contribution.
3. **Combined Probability/Likelihood Propagation**: implement probability propagation through the unified graph — reusing standard RBD series/parallel probability rules for physical branches, and a simplified likelihood scoring approach (e.g., attacker capability/opportunity scoring) for cyber branches — to produce an overall likelihood estimate for the top-event consequence.
4. **Critical Path Identification**: implement analysis to identify the lowest-effort path (physical, cyber, or combined) to the top-event consequence — directly supporting the CCE goal of identifying where "digital engineering-out" of a risk (removing or isolating a vulnerable digital dependency) would have the most impact.
5. **Mitigation Trade-off Analysis**: model how proposed mitigations (physical redundancy addition vs. cyber control addition, e.g., network segmentation) each affect the overall top-event likelihood, allowing direct comparison between physical and cyber mitigation investments in a common framework.

## Prerequisites / Background
- The Reliability Block Diagram methodology from the Avionics Electronics Reliability project
- Basic attack tree concepts (root goal, AND/OR decomposition of sub-goals, leaf-level attack steps) — conceptual level
- Graph theory basics (the natural unifying data structure for both RBDs and attack trees)

## Data / Dataset
- **Synthetic system model**: a representative, generic defense-style system described at block level, built for this project (and shared with CPS-01).
- **Public methodology**: INL's published Consequence-driven Cyber-Informed Engineering (CCE) materials; attack-step concepts from MITRE ATT&CK for ICS.
- **Parameters**: illustrative failure probabilities and attack-step likelihoods, clearly labeled as assumptions and varied in sensitivity analysis.

## Tech Stack
- Python, NetworkX (graph representation and analysis)
- Reuses the RBD probability propagation logic from the Avionics Electronics Reliability project
- Matplotlib/Plotly or Graphviz for unified diagram visualization

## Repository Structure
```
cyber-physical-rbd-attack-trees/
  src/
    unified_graph_model/
    consequence_driven_analysis/
    probability_likelihood_propagation/
    critical_path_identification/
    mitigation_tradeoff_analysis/
  external/                 # reused RBD module from Avionics Electronics Reliability
  docs/                     # explicit CCE methodology alignment notes
  notebooks/
  tests/
```

## Execution Plan
- [x] **Phase 1 — Unified graph representation**: design and implement the combined RBD/attack-tree graph data structure.
- [x] **Phase 2 — Consequence-driven modeling**: build out a representative synthetic system model starting from a defined top-event consequence, following CCE-style consequence-first analysis.
- [x] **Phase 3 — Probability/likelihood propagation**: implement propagation logic for both physical and cyber branches, validate against simple known RBD cases (all-physical scenario should exactly reduce to classical RBD results).
- [x] **Phase 4 — Critical path identification**: implement lowest-effort-path analysis across the unified graph.
- [x] **Phase 5 — Mitigation trade-off analysis**: model and compare physical vs. cyber mitigation options within the same framework.
- [ ] **Phase 6 — Documentation and publishing**: written methodology explanation with explicit, clear reference to the CCE framework as the inspiration and structure.

## Validation Strategy
- Physical-only sub-cases validated against classical RBD series/parallel probability formulas (exact match required).
- Unified model checked for logical consistency: adding an alternate (OR) path to the top event should never decrease its overall likelihood; adding a required (AND) step should never increase it.

## Deliverables
- Public repository with a documented, working unified RBD/attack-tree analysis tool
- A worked example applying consequence-driven analysis to a synthetic defense-representative system
- Visualizations: unified diagrams, critical path highlighting, mitigation trade-off comparisons

## Portfolio Differentiators
- Turns a well-known but rarely implemented methodological idea (unifying reliability and security risk modeling) into working, reusable software — most discussion of this idea exists only as consulting frameworks or slideware.
- Directly usable as a talking point connecting to the real CCE methodology practiced by organizations like INL, Black & Veatch, and Mission Secure — shows awareness of where the field is actually heading, not just a personal reinterpretation of "cyber plus reliability."

## Possible Extensions
- Apply the unified framework to the synthetic system already built in the Cyber Attack Impact Modeling project, producing a consistent, cross-project case study
- Extend likelihood scoring for cyber branches using a more formal framework (e.g., conceptual alignment with MITRE ATT&CK for ICS technique likelihood, at the effect level)
