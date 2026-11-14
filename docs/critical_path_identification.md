# Critical path identification

Code: [`src/cpsrbd/critical_path_identification/`](../src/cpsrbd/critical_path_identification/) ·
Lesson: [Lesson 4](lessons/04-the-lowest-effort-path.md) ·
Semantics: [Definitions 4–5, Proposition 6](formal-semantics.md) ·
Results: [`critical_path.md`](../validation/results/critical_path.md) ·
Tests: [`tests/test_critical_path.py`](../tests/test_critical_path.py)

## Minimal cut sets

`minimal_cut_sets(model)` expands the model bottom-up (OR: union of the children's families;
AND: pairwise unions; k-of-n: OR over k-subsets) and removes supersets at each node, memoising
shared nodes. The family equals what MOCUS (Fussell and Vesely, 1972) produces, and the top
event is the OR, over the family, of the AND of each set.

`describe` attaches to each cut set its probability (product), attacker cost (sum over cyber
steps), the probability of its physical preconditions, its composition and its kind
(physical, cyber or mixed).

## Three meanings of "lowest effort"

| ranking | function | metric | answers |
|---|---|---|---|
| most likely | `most_likely` | $-\ln P(C)$ | which scenario is most likely, regardless of origin |
| cheapest attack | `cheapest_attacks`, `min_attacker_cost` | summed attacker cost, cyber-only sets | what a targeted adversary would do; pays for a shared step once |
| opportunistic front | `opportunistic_front` | Pareto on (attacker cost, physical preconditions) | which mixed paths trade effort for luck |

`activated(model, events)` returns every node that a scenario triggers, for drawing.

## Importance measures

`importance_measures(model)` returns, for every basic event, Birnbaum
$Q(1_i) - Q(0_i)$, criticality, exact Fussell–Vesely (probability of the union of the cut sets
containing the event, divided by $Q$), RAW $Q(1_i)/Q$ and RRW $Q/Q(0_i)$. For a cyber step,
$Q(0_i)$ (`q_without`) is the risk left after **engineering it out**.
