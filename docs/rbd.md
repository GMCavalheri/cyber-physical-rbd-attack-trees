# Reliability block diagrams

Code: [`src/cpsrbd/rbd/diagram.py`](../src/cpsrbd/rbd/diagram.py) ·
Lesson: [Lesson 1](lessons/01-two-languages-for-one-failure.md) ·
Semantics: [Theorem 1](formal-semantics.md) ·
Tests: [`tests/test_rbd.py`](../tests/test_rbd.py)

## Structures and closed forms

An RBD is written in success logic: `Block(name, R)`, `Series`, `Parallel`, `KofN(k, ...)`, and
`PathSets` for structures that are not series-parallel (the `bridge` helper builds the classical
five-component bridge). For independent, distinct blocks:

```math
R_{\text{series}} = \prod_i R_i, \qquad
R_{\text{parallel}} = 1 - \prod_i (1 - R_i), \qquad
R_{k/n} = P\Bigl(\textstyle\sum_i X_i \ge k\Bigr)
```

where the last one is a Poisson-binomial tail, computed by a one-pass recursion
(`at_least_k`); `k_out_of_n_identical` gives the binomial sum for identical blocks.
`bridge_reliability` pivots on the cross-link; for identical blocks it reduces to
$2R^2 + 2R^3 - 5R^4 + 2R^5$ (Rausand and Høyland, 2004, §4.6).

`reliability()` refuses a diagram in which a block appears twice, since the product formulas
assume independent branches.

## Conversion to the unified model

`to_unified(rbd)` applies De Morgan's laws:

| RBD (works if ...) | unified (fails if ...) |
|---|---|
| series: every block works | OR of failures |
| parallel: any block works | AND of failures |
| k-of-n: at least k work | at least $n - k + 1$ fail |
| path sets: all blocks of some path work | AND over paths of OR over the path's blocks |

Each block becomes a physical event with $p = 1 - R$; a repeated block becomes one shared event.
Theorem 1 proves the conversion exact for every state; the tests check it state by state on
random RBDs, and the propagation tests check $Q = 1 - R$ to 1e-12.

## Why it is here

The plan expected to reuse the RBD code of an avionics reliability project in this portfolio,
which has not been built. This module stands alone, so that project can import it later.
