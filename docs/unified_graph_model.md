# Unified graph model

Code: [`src/cpsrbd/unified_graph_model/`](../src/cpsrbd/unified_graph_model/) ·
Lesson: [Lesson 1](lessons/01-two-languages-for-one-failure.md) ·
Semantics: [formal semantics, §1–3](formal-semantics.md) ·
Tests: [`tests/test_unified_graph_model.py`](../tests/test_unified_graph_model.py)

## What it is

A `UnifiedModel` is a directed acyclic graph with one top event. Gates (`AND`, `OR`, `KOFN`)
combine their children in **failure logic**: a node is true when its undesired event happens.
Leaves are `BasicEvent`s with an **origin**, an occurrence probability for the analysis window,
and an attacker cost:

| origin | probability from | cost |
|---|---|---|
| physical (`physical_event`) | a probability, or $p = 1 - e^{-\lambda t}$ from a rate and exposure time | $\infty$ (the attacker cannot buy a random failure) |
| cyber (`cyber_step`) | an illustrative likelihood score (see [consequence-driven analysis](consequence_driven_analysis.md)) | attacker effort, e.g. analyst-weeks |

Metadata (rate, scores, ATT&CK for ICS technique, source of the number) goes in
`BasicEvent.attributes` and is carried into reports.

## Main operations

| method | purpose |
|---|---|
| `add_event`, `add_gate`, `and_`, `or_`, `kofn` | build; names are unique |
| `validate()` | top exists, children exist and are distinct, $1 \le k \le n$, acyclic, all nodes reachable |
| `structure_function(failed)` | the Boolean value of the top event for one state |
| `bottom_up()`, `path_counts()`, `shared_events()`, `is_tree()` | traversal; a basic event with more than one path from the top is *shared* |
| `with_event`, `with_gate`, `pruned`, `rooted_at`, `copy` | edits that return copies (the baseline is never mutated) |
| `graph()` | export to a NetworkX `DiGraph` with node attributes |

## Design choices

* **Failure logic throughout.** Fault trees and attack trees both use it; RBDs are converted
  into it exactly (see [RBD](rbd.md)).
* **A DAG, not a tree.** Shared dependencies (a power bus, a maintenance laptop) are one node
  with several parents, which keeps the probabilities exact (Lesson 3).
* **Immutable from the caller's view.** Mitigation analysis compares hundreds of variants of one
  model, so every edit returns a copy.
* **No NOT gate.** The model is coherent (monotone), which the cut-set, importance and
  mitigation analyses rely on; the cost is that antagonistic interactions cannot be expressed
  ([formal semantics, §7](formal-semantics.md)).

## Drawing

[`plotting.draw_model`](../src/cpsrbd/plotting.py) draws any model with a layered layout (depth =
longest distance from the top; barycentre sweeps to reduce crossings) using matplotlib only.
Gates are grey squares, physical events blue circles, cyber steps red diamonds; `highlight`
marks a scenario and the gates it triggers.
