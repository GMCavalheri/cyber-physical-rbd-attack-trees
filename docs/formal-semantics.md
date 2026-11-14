# Formal semantics of the unified model

This note defines the unified RBD/attack-tree model precisely, states what it reduces to in
the all-physical and all-cyber cases, and proves the properties the analyses rely on. It is the
technical core of the RES-02 paper plan. Every statement here is checked numerically on random
models by [`validation/reduction_checks.py`](../validation/reduction_checks.py) (results in
[`reduction_checks.md`](../validation/results/reduction_checks.md)) and by the Hypothesis tests
named next to it.

## 1. Syntax

**Definition 1 (unified model).** A unified model is a tuple

```math
M = (E, G, t, \kappa, \mathrm{ch}, k, o, p, c)
```

where

* $E$ is a finite set of **basic events** and $G$ a finite set of **gates**, disjoint;
* $t \in E \cup G$ is the **top event**;
* $\kappa : G \to \{\mathrm{AND}, \mathrm{OR}, \mathrm{VOT}\}$ gives each gate its type;
* $\mathrm{ch} : G \to (E \cup G)^{+}$ gives each gate a non-empty sequence of distinct
  children;
* $k : \kappa^{-1}(\mathrm{VOT}) \to \mathbb N$ gives each voting gate $g$ a threshold
  $1 \le k(g) \le |\mathrm{ch}(g)|$;
* $o : E \to \{\mathrm{phys}, \mathrm{cyber}\}$ is the **origin** of each basic event;
* $p : E \to [0, 1]$ is its probability of occurring within the analysis window;
* $c : E \to [0, \infty]$ is the attacker's cost to cause it, with $c(e) = \infty$ whenever
  $o(e) = \mathrm{phys}$.

The graph with an edge from each gate to each of its children must be **acyclic**, and every
node must be reachable from $t$. It is a DAG, not necessarily a tree: a node may have several
parents. A basic event reachable from $t$ by more than one path is **shared**.

In the code, `UnifiedModel.validate()` enforces exactly these conditions
([`model.py`](../src/cpsrbd/unified_graph_model/model.py)).

## 2. Semantics

**Definition 2 (structure function).** A **state** is a vector $z \in \{0,1\}^E$, where
$z_e = 1$ means event $e$ occurred. Each node $n$ gets a value $\Phi_n(z)$:

```math
\Phi_e(z) = z_e, \qquad
\Phi_g(z) = \mathbb 1\Bigl[\textstyle\sum_{n \in \mathrm{ch}(g)} \Phi_n(z) \ge \theta(g)\Bigr],
\qquad
\theta(g) = \begin{cases} |\mathrm{ch}(g)| & \kappa(g) = \mathrm{AND} \\ 1 & \kappa(g) = \mathrm{OR} \\ k(g) & \kappa(g) = \mathrm{VOT} \end{cases}
```

The model's structure function is $\Phi = \Phi_t$. Because the graph is acyclic this
recursion is well defined.

**Definition 3 (probabilistic semantics).** The basic events are independent Bernoulli
variables $Z_e \sim \mathrm{Bernoulli}(p(e))$. The top-event probability is

```math
Q(M) = P\bigl(\Phi(Z) = 1\bigr) = \sum_{z \in \{0,1\}^E} \Phi(z) \prod_{e \in E} p(e)^{z_e}\bigl(1 - p(e)\bigr)^{1 - z_e}.
```

This sum is the definition; `enumerate_probability` computes it literally and is the oracle
for every other method.

**Definition 4 (cut sets).** A set $C \subseteq E$ is a **cut set** if
$\Phi(\mathbb 1_C) = 1$, where $\mathbb 1_C$ is the state in which exactly the events of $C$
occur. It is **minimal** if no proper subset is a cut set. $\mathcal C(M)$ is the family of
minimal cut sets. A minimal cut set is **physical**, **cyber** or **mixed** according to the
origins of its events.

**Definition 5 (attacker cost).** The exact minimum attacker cost is

```math
c^{*}(M) = \min_{C \in \mathcal C(M)} \sum_{e \in C} c(e),
```

which is $\infty$ when every minimal cut set contains a physical event.

## 3. Basic properties

**Proposition 1 (coherence).** $\Phi$ is monotone: $z \le z'$ componentwise implies
$\Phi(z) \le \Phi(z')$. Consequently $Q$ is non-decreasing in every $p(e)$, and
$\Phi(z) = 1$ if and only if $z \ge \mathbb 1_C$ for some $C \in \mathcal C(M)$.

*Proof.* Every gate function $u \mapsto \mathbb 1[\sum u \ge \theta]$ is monotone, and
compositions of monotone functions are monotone; induction over a topological order of the
DAG gives the first claim. $Q$ is multilinear in the $p(e)$, and
$\partial Q / \partial p(e) = P(\Phi = 1 \mid Z_e = 1) - P(\Phi = 1 \mid Z_e = 0) \ge 0$ by
monotonicity. For the last claim: if $\Phi(z) = 1$, the set $\{e : z_e = 1\}$ is a cut set and
contains a minimal one; conversely, if $z \ge \mathbb 1_C$ then
$\Phi(z) \ge \Phi(\mathbb 1_C) = 1$. ∎

Tests: `test_raising_any_leaf_never_lowers_the_top`,
`test_cut_sets_represent_the_structure_function_exactly`.

## 4. Reduction to the classical models

**Definition 6 (RBD).** A reliability block diagram is a term of the grammar

```math
R ::= \mathrm{Block}(b, r) \mid \mathrm{Series}(R_1, \dots, R_n) \mid \mathrm{Parallel}(R_1, \dots, R_n) \mid \mathrm{KofN}(k; R_1, \dots, R_n) \mid \mathrm{Paths}(B; \mathcal P)
```

with success structure function $\varphi_R(x)$ over block states $x \in \{0,1\}^B$ ($x_b = 1$:
block $b$ works): $\min$ for series, $\max$ for parallel, $\mathbb 1[\sum \ge k]$ for k-of-n,
and $\max_{P \in \mathcal P} \min_{b \in P} x_b$ for a structure given by its minimal path
sets $\mathcal P$. With independent blocks of reliability $r(b)$, the system reliability is
$\mathcal R(R) = P(\varphi_R(X) = 1)$.

**Definition 7 (dual conversion).** $\tau(R)$ maps an RBD to a unified model whose basic
events are the blocks, all physical, with $p(b) = 1 - r(b)$, and whose gates are

| RBD term | unified gate |
|---|---|
| $\mathrm{Series}(R_1..R_n)$ | $\mathrm{OR}(\tau R_1, \dots, \tau R_n)$ |
| $\mathrm{Parallel}(R_1..R_n)$ | $\mathrm{AND}(\tau R_1, \dots, \tau R_n)$ |
| $\mathrm{KofN}(k; R_1..R_n)$ | $\mathrm{VOT}(n-k+1;\ \tau R_1, \dots, \tau R_n)$ |
| $\mathrm{Paths}(B; \mathcal P)$ | $\bigwedge_{P \in \mathcal P} \bigvee_{b \in P} b$ |

A block name used more than once becomes one shared event (`rbd.to_unified`).

**Theorem 1 (all-physical reduction).** For every RBD $R$,
$\Phi_{\tau(R)}(\mathbf 1 - x) = 1 - \varphi_R(x)$ for every state $x$, and therefore

```math
Q\bigl(\tau(R)\bigr) = 1 - \mathcal R(R).
```

*Proof.* By structural induction, with $z = \mathbf 1 - x$ (an event "occurs" when its block
fails). Block: $\Phi_b(z) = z_b = 1 - x_b$. Series: $1 - \min_i \varphi_i = \max_i (1 - \varphi_i)$,
which is the OR of the converted children by the induction hypothesis. Parallel:
$1 - \max_i \varphi_i = \min_i(1 - \varphi_i)$, the AND. k-of-n: fewer than $k$ children work if
and only if at least $n - k + 1$ children fail, which is a voting gate with threshold $n - k + 1$. Paths: the
structure fails if and only if every path set contains a failed block, the AND over paths of
the OR over their blocks. Each step is De Morgan's law or a counting identity, so the
correspondence holds for every state. Since the block failures $1 - X_b$ are independent
Bernoulli$(1 - r(b))$ variables, i.e. distributed as $Z$ under Definition 3, taking
expectations gives $Q(\tau R) = E[1 - \varphi_R(X)] = 1 - \mathcal R(R)$. ∎

When a block is repeated, $\mathcal R(R)$ is still defined by the structure function (the
textbook product formulas no longer apply), and the theorem still holds.

Tests: `test_duality_*` (every state), `test_all_physical_models_reduce_exactly_to_the_rbd`.
Seeded check: maximum error 2.2e-16 over 400 random RBDs.

**Definition 8 (attack tree).** A classical attack tree is a term
$T ::= \mathrm{Step}(a, p_a, c_a) \mid \mathrm{AND}(T_1..T_n) \mid \mathrm{OR}(T_1..T_n)$.
Following Mauw and Oostdijk (2005), reduced to sets, its semantics $[\![T]\!]$ is the family of
minimal attack scenarios:

```math
[\![a]\!] = \{\{a\}\}, \quad
[\![\mathrm{OR}(T_i)]\!] = \min \textstyle\bigcup_i [\![T_i]\!], \quad
[\![\mathrm{AND}(T_i)]\!] = \min \{S_1 \cup \dots \cup S_n : S_i \in [\![T_i]\!]\},
```

where $\min$ removes every set that strictly contains another. Its classical quantitative
attributes are computed bottom-up: probability with OR as $1 - \prod(1 - \cdot)$ and AND as
$\prod$, minimum cost with OR as $\min$ and AND as $\sum$.

**Theorem 2 (all-cyber reduction).** Let $\sigma(T)$ be the unified model with the same gates
and one cyber basic event per step name (`attack_tree.to_unified`). Then

* (a) $\mathcal C(\sigma T) = [\![T]\!]$;
* (b) if no step name repeats (a tree), $Q(\sigma T)$ equals the classical bottom-up
  probability;
* (c) if no step name repeats, $c^{*}(\sigma T)$ equals the classical bottom-up minimum cost.
  With repeated steps, $c^{*}(\sigma T)$ is at most the classical value.

*Proof.* (a) The bottom-up computation of minimal cut sets in
[`cut_sets.py`](../src/cpsrbd/critical_path_identification/cut_sets.py) is literally the
recursion of Definition 8 (union for OR, pairwise unions for AND, then minimisation). That it
computes $\mathcal C$ follows from Proposition 1: a node's family represents its sub-function
in disjunctive normal form, the operations preserve that, and absorption ($A \vee (A \wedge B)
= A$) is exactly the removal of supersets. (b) In a tree, the children of each gate depend on
disjoint sets of independent events, so they are independent and the bottom-up formulas are
exact; Theorem 3 below then gives the same value. (c) In a tree, every minimal cut set of an
AND node is a disjoint union of one minimal cut set per child, so the minimum of the summed
cost splits into the sum of the children's minima; for OR it is the minimum over the union.
With a repeated step, the classical bottom-up value pays for the step once per occurrence,
while $c^{*}$ pays once per set, so $c^{*} \le$ classical. ∎

Tests: `test_theorem_2_all_cyber_trees_reduce_to_classical_attack_trees`,
`test_shared_steps_semantics_still_agree_but_bottom_up_numbers_do_not`. Seeded check: zero
mismatches and zero numerical error over 400 random trees.

The two theorems are the necessary correctness condition RES-02 asks for: the unified model
is a conservative extension of both classical models. Nothing a reliability engineer or a
security analyst computes in their own formalism changes when their model is embedded in it.

## 5. Exact computation on DAGs

**Theorem 3 (Shannon conditioning on shared events is exact).** Let
$S \subseteq E$ be the set of shared basic events. For each assignment $s \in \{0,1\}^S$, let
$B(s)$ be the bottom-up probability of the top event, computed with the independence
formulas, after setting $p(e) = s_e$ for $e \in S$. Then

```math
Q(M) = \sum_{s \in \{0,1\}^S} B(s) \prod_{e \in S} p(e)^{s_e}\bigl(1 - p(e)\bigr)^{1 - s_e}.
```

*Proof.* By the law of total probability over the values of $Z_S$, it suffices to show that
$B(s) = P(\Phi(Z) = 1 \mid Z_S = s)$. Given $Z_S = s$, every remaining random event is reached
by exactly one path from $t$. Take any gate $g$ and two of its children $u \ne v$. If a free
event $e$ were below both, $e$ would have two distinct paths from $t$ (through $u$ and through
$v$), so it would be shared and fixed; hence the free events below different children are
disjoint, and the children's values are conditionally independent. A gate reached by several
paths has only shared events below it (each of its descendants inherits its paths), so its
value is a constant given $s$, and the formulas handle constants correctly. Applying the
independence formulas from the leaves up is therefore exact at every gate. ∎

The cost is $2^{|S|}$ bottom-up passes. Binary decision diagrams (Rauzy, 1993) apply the same
expansion with sharing of identical sub-results and scale much further; the semantics is
identical.

Tests: `test_exact_equals_enumeration_on_random_dags`. Seeded check: maximum error 1.0e-15
over 400 random DAGs, while the plain tree formulas are off by up to 0.23 on the same DAGs.

## 6. Properties used by the analyses

**Proposition 4 (monotone design changes).** Let $M'$ be $M$ with one new child $x$
(independent of everything else) added to an existing gate $g$. If $\kappa(g) = \mathrm{OR}$,
then $Q(M') \ge Q(M)$. If $\kappa(g) = \mathrm{AND}$, then $Q(M') \le Q(M)$.

*Proof.* For OR, $\Phi'_g = \Phi_g \vee z_x \ge \Phi_g$ pointwise; for AND,
$\Phi'_g = \Phi_g \wedge z_x \le \Phi_g$. Monotonicity of the rest of the structure
(Proposition 1) carries the inequality to the top event, pointwise in $z$, and hence in
expectation. ∎

This is the plan's logical-consistency requirement: an alternative path never makes the
consequence less likely, and an extra required step never makes it more likely. It also proves
that every mitigation of Lesson 5 moves the risk in the stated direction: `RequireStep` adds an
AND child; `AddRedundancy` replaces an event by an AND of two (with an OR to a smaller
common-cause event); `ReduceProbability` and `EngineerOut` lower a probability.

**Proposition 5 (interaction gap).** Let $Q_{\mathrm{phys}}$ be $Q$ with $p(e) = 0$ for every
cyber event, and $Q_{\mathrm{cyber}}$ the same for every physical event. Define

```math
\Gamma(M) = Q(M) - \bigl[1 - (1 - Q_{\mathrm{phys}})(1 - Q_{\mathrm{cyber}})\bigr].
```

Then $\Gamma(M)$ is the probability that the top event occurs while no physical-only and no
cyber-only minimal cut set has fully occurred. In particular $\Gamma(M) \ge 0$, with equality
when $M$ has no mixed minimal cut set of positive probability.

*Proof.* Let $A_{\mathrm{phys}}$ be the event that some physical minimal cut set has fully
occurred, and $A_{\mathrm{cyber}}$ the same for cyber ones. Setting all cyber probabilities to
zero removes exactly the cut sets that contain a cyber event (Proposition 1), so
$Q_{\mathrm{phys}} = P(A_{\mathrm{phys}})$, and likewise $Q_{\mathrm{cyber}} = P(A_{\mathrm{cyber}})$.
$A_{\mathrm{phys}}$ depends only on physical events and $A_{\mathrm{cyber}}$ only on cyber events,
so they are independent and
$P(A_{\mathrm{phys}} \cup A_{\mathrm{cyber}}) = 1 - (1 - Q_{\mathrm{phys}})(1 - Q_{\mathrm{cyber}})$.
Both are sub-events of $\{\Phi = 1\}$, so
$\Gamma = P(\Phi = 1) - P(A_{\mathrm{phys}} \cup A_{\mathrm{cyber}}) = P(\Phi = 1 \setminus (A_{\mathrm{phys}} \cup A_{\mathrm{cyber}})) \ge 0$.
If no mixed cut set has positive probability, then almost surely $\Phi = 1$ only through a
pure cut set, and $\Gamma = 0$. ∎

$\Gamma$ measures exactly the risk that two separate analyses, one reliability model and one
attack tree, cannot see even when their results are combined correctly. In the case study it
is 3.16e-4, **31 %** of the total (`origin_decomposition`).

Tests: `test_proposition_5_interaction_gap` (against an enumeration of its definition).
Seeded check: maximum error 5.6e-16, no negative values, over 400 random mixed DAGs.

**Proposition 6 (exact attacker cost on DAGs).** For any model, $c^{*}(M)$ is at most the
bottom-up min-sum value, with equality on trees.

*Proof.* The bottom-up min-sum value is the minimum, over the cut sets generated by the
expansion *as multisets*, of the cost summed with multiplicity. Each such multiset dominates a
minimal cut set of no greater cost, since costs are non-negative and absorption only removes
events. On a tree there are no repeated events, so the two minima coincide (Theorem 2c). ∎

Tests: `test_min_cost_over_cut_sets_bounds_the_bottom_up_value`,
`test_shared_step_is_paid_once` (bottom-up 22 against exact 12).

## 7. What the semantics does not cover

* **Order and time.** The model is static: AND means "all happen within the window", not "in
  this order". Sequential AND (SAND) gates, dynamic fault-tree gates and attack timing need a
  dynamic semantics (attack-fault trees, BDMPs; see [`related-work.md`](related-work.md)).
* **Negation.** Without NOT gates the model cannot express antagonism (a safety measure that
  helps the attacker, such as a door that unlocks on fire alarm). That is the price of
  coherence, which Propositions 1, 4 and 6 depend on.
* **Dependence between cyber steps.** Steps are independent Bernoulli variables. A real
  attacker adapts: success at one step changes the odds of the next. Conditional step
  probabilities can be encoded by restructuring the tree, but the semantics does not model an
  adaptive adversary.
* **Meaning of cyber probabilities.** $p(e)$ for a cyber step is a judgement-based likelihood,
  given an attempt by the considered threat actor. The algebra is the same as for physical
  failures, but the epistemic status is not (see [`scope.md`](scope.md) and Lesson 2).

## References

* R. E. Barlow and F. Proschan, *Statistical Theory of Reliability and Life Testing*, 1975.
* S. Mauw and M. Oostdijk, "Foundations of attack trees", ICISC 2005, LNCS 3935, 2006.
* A. Rauzy, "New algorithms for fault trees analysis", *RESS*, 40(3), 1993.
* M. Rausand and A. Høyland, *System Reliability Theory*, 2nd ed., Wiley, 2004.
* C. E. Shannon, "The synthesis of two-terminal switching circuits", *Bell System Technical
  Journal*, 28(1), 1949.
