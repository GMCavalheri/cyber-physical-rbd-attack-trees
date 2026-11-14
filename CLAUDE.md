# CLAUDE.md

One graph for physical failure and cyber attack: reliability block diagrams (RBD) and attack
trees unified into a single DAG rooted at a system-level consequence, following
Consequence-driven Cyber-Informed Engineering (CCE). Probability propagation, critical
(lowest-effort) paths, and physical-vs-cyber mitigation trade-offs on one model.
Plan: `CPS-02-cyber-physical-rbd-attack-trees-PLAN.md` (tick the phase checkboxes as phases
land). This repository is also the software base of the RES-02 methodology paper, so the
formal semantics (`docs/formal-semantics.md`) and the code must agree.

## Commands
- `uv sync` — install (Python ≥ 3.11; CI runs 3.11, 3.12 and 3.13)
- `uv run pytest --cov` — tests with the 90 % coverage gate
- `uv run ruff check . && uv run ruff format --check .` — lint/format. Ruff also formats the
  ```python blocks inside Markdown, so run it after editing docs too
- `uv run mypy` — strict type check of `src/`
- `uv run python validation/<script>.py` — regenerate one phase's tables
  (`validation/results/`) and figures (`docs/figures/`); `validation/run_all.py` runs them all
- `uv run python notebooks/build_notebooks.py` — regenerate and execute the notebooks

## Layout
- `src/cpsrbd/` — single package; subpackages mirror the plan:
  `unified_graph_model` (the DAG, gates, basic events), `rbd` (classical success-space RBDs and
  their exact conversion to the unified model), `consequence_driven_analysis` (CCE-style
  builder and the synthetic case study), `probability_likelihood_propagation`,
  `critical_path_identification`, `mitigation_tradeoff_analysis`; plus `plotting.py`.
- `src/cpsrbd/data/` — case-study parameters (CSV); every value is labelled an assumption or
  carries its source.
- `tests/` — pytest + Hypothesis. `validation/` — one script per phase, `results/` tables.
- `docs/` — theory note per module, `scope.md`, `formal-semantics.md`, `related-work.md`,
  `methodology.md`; `docs/lessons/` is the course (keep its numbers in sync with
  `validation/results/`). `notebooks/` — one executed demo per lesson.

## Conventions
- The unified model is written in **failure (consequence) logic**, like a fault tree: a node
  is "true" when its undesired event happens. RBDs are authored in success logic and converted
  exactly by duality (series → OR of failures, parallel → AND, k-of-n good → (n−k+1)-of-n
  failed).
- Basic events are independent Bernoulli variables over the analysis window. Physical events
  get their probability from a failure rate and an exposure time; cyber steps from an
  explicitly illustrative likelihood score. Never present a cyber likelihood as field data.
- Probabilities are float64. Exact results (closed forms, Shannon decomposition) are compared
  with tolerance 1e-12; Monte Carlo against its own confidence interval.
- Models are immutable from the caller's point of view: mitigations return modified copies.

## Scope (public repo)
- Synthetic system, public methodology (INL CCE/CIE, MITRE ATT&CK for ICS) only. Cyber steps
  are modelled at the **effect level** (what an attack does to the system), never as exploit
  procedures. See `docs/scope.md`.
- Never mention the author's employer or day job in any file, commit message or doc.

## Docs (GitHub-rendered math)
- Display equations go in ```` ```math ```` fences (no Markdown processing inside).
- Inline `$...$` is processed as Markdown first: no `\,` or `\;`, no `\\` row breaks, and no
  `_` right after `}` `)` `]`. `tests/test_docs.py` guards this.

## Testing rules
- Every test asserts against a closed-form result, an independent oracle (brute-force
  enumeration) or a cited published value; name the source in a comment.
- Never loosen a tolerance to make a failing test pass without explaining why.
- Properties that must hold for every model (coherence/monotonicity, reductions to the
  classical RBD and attack tree) are Hypothesis tests over random models.

## Workflow
- Commit small logical changes directly to `main`; push after ruff, mypy and pytest pass,
  each run as its own command (no pipes: a pipe hides the exit code). Stage explicit paths.
- Each phase lands as code + tests, then validation results, then its lesson in
  `docs/lessons/` as a separate commit. Confirm CI is green after each push.
