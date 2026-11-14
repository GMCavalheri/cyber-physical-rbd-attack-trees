# Mitigation trade-off analysis

Code: [`src/cpsrbd/mitigation_tradeoff_analysis/`](../src/cpsrbd/mitigation_tradeoff_analysis/) ·
Lesson: [Lesson 5](lessons/05-comparing-mitigations.md) ·
Results: [`mitigation.md`](../validation/results/mitigation.md) ·
Tests: [`tests/test_mitigation.py`](../tests/test_mitigation.py)

## Mitigations are model transformations

| class | transformation | category |
|---|---|---|
| `AddRedundancy(events, beta)` | each event becomes OR(AND(unit a, unit b), common cause), units at $(1-\beta)q$, common cause at $\beta q$ | physical |
| `ReduceProbability(event, factor, added_cost)` | $q \to fq$, $c \to c + \Delta c$ | physical or cyber |
| `RequireStep(target, step)` | parents of the target now see AND(target, new step) | cyber |
| `EngineerOut(events)` | $q \to 0$, $c \to \infty$ | engineer-out |

Each has a name, an investment (illustrative units) and a category. Proposition 4 of the
[formal semantics](formal-semantics.md) guarantees that each moves the risk in the stated
direction; Hypothesis tests check it on random models.

## Analyses

* `assess(model, options)`: each option alone — risk before and after, relative reduction,
  reduction per unit invested, cheapest attack before and after.
* `portfolios(model, options)`: every subset (up to 12 options, $2^n$ portfolios), evaluated
  exactly; `pareto_front(..., "risk" | "effort")` and `best_within_budget` pick from them.
* `tornado(model, factor)`: one-at-a-time sensitivity of $Q$ to each input.
* `uncertainty_samples(model, options, samples, seed)`: redraws every probability from a
  lognormal around its nominal value (error factor 3 for physical, 10 for cyber by default,
  $\sigma = \ln \mathrm{EF}/1.645$) and evaluates every option on the same draws.

The catalogue for the case study is in
[`catalogue.py`](../src/cpsrbd/mitigation_tradeoff_analysis/catalogue.py); every number in it
is an assumption, and every option is described by its effect on the model.
