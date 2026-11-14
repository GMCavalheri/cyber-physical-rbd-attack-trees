# Probability and likelihood propagation

Code: [`src/cpsrbd/probability_likelihood_propagation/`](../src/cpsrbd/probability_likelihood_propagation/) ·
Lessons: [Lesson 3](lessons/03-propagating-probability-and-likelihood.md),
[Lesson 6](lessons/06-formal-semantics-and-what-is-new.md) ·
Semantics: [Theorem 3, Proposition 5](formal-semantics.md) ·
Results: [`propagation.md`](../validation/results/propagation.md) ·
Tests: [`tests/test_propagation.py`](../tests/test_propagation.py)

## Methods

| function | result | exact? | cost |
|---|---|---|---|
| `bottom_up_probability` | independence formulas at each gate | on trees only | linear |
| `exact_probability` | Shannon decomposition on the $s$ shared events | always | $2^s$ bottom-up passes |
| `enumerate_probability` | sum of the structure function over all states | always (oracle) | $2^n$ states, $n \le 22$ |
| `monte_carlo_probability` | sampled estimate with a 95 % Wilson interval | statistical | vectorised, seeded |
| `conditional_probability` | P(TOP) given some events fixed | always | as exact |

Gate formulas for independent children: AND $\prod q_i$, OR $1 - \prod(1 - q_i)$, k-of-n the
Poisson-binomial tail. On a DAG the tree formulas underestimate when a shared event sits under
an AND (the common-cause trap) and overestimate under an OR.

## Views and the interaction gap

`origin_overrides(model, keep)` switches off every event of the other origin. Together they give
`origin_decomposition(model)`: the full probability, the physical-only (reliability) view, the
cyber-only (attack-tree) view, their combination as independent risks, and the **interaction
gap** — the probability that the consequence happens only through mixed scenarios
(Proposition 5).

## Attribute domains

`evaluate(model, domain)` computes Mauw–Oostdijk-style attributes bottom-up: `PROBABILITY`,
`MIN_COST` (OR min, AND sum), `MOST_LIKELY` (OR max, AND product) and `POSSIBLE` (can the
attacker do it alone?). These use tree semantics; on DAGs the exact values come from minimal
cut sets ([critical path identification](critical_path_identification.md)).
