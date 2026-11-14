# Consequence-driven analysis

Code: [`src/cpsrbd/consequence_driven_analysis/`](../src/cpsrbd/consequence_driven_analysis/) ·
Lesson: [Lesson 2](lessons/02-start-from-the-consequence.md) ·
Data: [`case_study_parameters.csv`](../src/cpsrbd/data/case_study_parameters.csv) ·
Results: [`case_study.md`](../validation/results/case_study.md) ·
Tests: [`tests/test_consequence_driven_analysis.py`](../tests/test_consequence_driven_analysis.py)

## Building consequence first

`ConsequenceBuilder(Consequence(name, statement))` develops the model top-down with `any_of`,
`all_of` and `at_least`. A node can only be developed after something refers to it, and
`build()` fails while any referenced cause is undeveloped (`undeveloped()` lists them). This
enforces the CCE discipline of walking backward from the consequence without leaving a branch
half-analysed.

Structural queries:

* `branch_origins` / `branch_kinds` mark every gate *physical-only*, *cyber-only* or *mixed*;
* `paths_to(model, node)` lists every path from the consequence down to a node.

## Likelihood scoring for cyber steps

Two expert scores on 1–5 scales, capability required ($a$) and opportunity ($o$), give
$s = o + (6 - a) \in [2, 10]$, mapped log-linearly onto a band $[p_{\text{low}}, p_{\text{high}}]$
(default [1e-4, 1e-1]):

```math
\log_{10} p(s) = \log_{10} p_{\text{low}} + \left(\log_{10} p_{\text{high}} - \log_{10} p_{\text{low}}\right)\frac{s - 2}{8}.
```

The scale and the band are explicit **assumptions**, varied in the sensitivity analysis. The
number is the chance a step succeeds within the window given a capable adversary is trying;
it supports comparison, not forecasting.

## The case study

`navigation_case_study(mission_hours=10, band=..., parameters=None)` builds the synthetic model:
the consequence *"the mission computer loses trustworthy navigation data during the mission"*,
covering loss of availability (sources, data path, computer) and loss of integrity (accepted
spoofed GNSS, injected bus messages). 15 gates, 8 physical events, 7 effect-level cyber steps
tagged with ATT&CK for ICS technique IDs, 4 shared events. Every CSV row states its basis, and
`load_parameters` rejects rows without one. See [`scope.md`](scope.md) for the publishing
boundaries.
