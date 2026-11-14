# Lesson 6 · Formal semantics, and what is (and isn't) new

> Five lessons built and used a model. This one asks two questions a reviewer will ask. First:
> what exactly does the model *mean*, and can you prove that it agrees with the methods
> engineers already trust? Second: what is actually new here, given forty years of fault trees,
> twenty-five of attack trees, and fifteen of attempts to combine them? Answering the first
> takes definitions and proofs. Answering the second takes a literature review and the
> discipline to claim less than you would like to.

**Read alongside:** [`docs/formal-semantics.md`](../formal-semantics.md) (definitions,
theorems, proofs) and [`docs/related-work.md`](../related-work.md) (the comparison) ·
**Code:** [`attack_tree.py`](../../src/cpsrbd/attack_tree.py),
[`origin_decomposition`](../../src/cpsrbd/probability_likelihood_propagation/probability.py) ·
**Results:** [`validation/results/reduction_checks.md`](../../validation/results/reduction_checks.md) ·
**Previous:** [Lesson 5](05-comparing-mitigations.md)

## Learning objectives

1. Separate a model's *syntax* (what you can draw) from its *semantics* (what it means), and
   say why a methodology paper needs both.
2. State the conservative-extension property and explain why it is the correctness
   condition for a unified model.
3. Prove the all-physical and all-cyber reductions, and test them independently.
4. Define the interaction gap and prove it is a probability.
5. Position a contribution honestly against related work, including what the model *cannot*
   express.

---

## 1. Why semantics?

A diagram is not a model until each element has a precise meaning. Two analysts can draw the
same attack tree and compute different numbers if one treats a repeated step as one event and
the other as two. Formal semantics removes that ambiguity:

* **Syntax** says what a model is made of: events, gates, a top event, an acyclic graph,
  origins, probabilities and costs ([formal semantics, §1](../formal-semantics.md)).
* **Semantics** says what it means: a Boolean **structure function** $\Phi$ on event states,
  a **probability** $Q = P(\Phi(Z) = 1)$ under independent events, and the family
  $\mathcal C$ of **minimal cut sets** (§2).

The definition of $Q$ is a sum over all $2^n$ states. That makes it the ground truth, and
every faster algorithm in the repository must be **proved** equal to it (Shannon
decomposition, Theorem 3) or **bounded** by it (bottom-up formulas on DAGs, rare-event sums).

## 2. The correctness condition: a conservative extension

A unified model is only acceptable if it does not change the answers of the models it
unifies. In logic, a theory that adds new vocabulary without changing what the old vocabulary
proves is a **conservative extension**. Here that means two theorems.

**Theorem 1 (all-physical).** Convert any RBD by duality; the converted model's top-event
probability is exactly $1 - R$. The proof is a structural induction in which each case is De
Morgan's law or a counting identity, so it holds state by state, not just on average.

**Theorem 2 (all-cyber).** Convert any classical attack tree; the minimal cut sets equal the
Mauw–Oostdijk attack scenarios, and the probability and minimum cost equal the classical
bottom-up values. With a repeated step, the scenarios still agree, and the exact minimum cost
is never above the classical one.

Proving them is half the job. The other half is checking that the **code** implements what was
proved. The trick is an **independent reference**:
[`attack_tree.py`](../../src/cpsrbd/attack_tree.py) implements classical attack trees from
their textbook definitions, sharing no code with the unified model. If the unified analyses
agree with it on hundreds of random trees, a bug would have to appear identically in two
unrelated implementations. The seeded results:

| statement | random models | worst case |
|---|---|---|
| Theorem 1: $Q = 1 - R$ | 400 RBDs | 2.2e-16 |
| Theorem 2a: cut sets = attack scenarios | 400 trees | 0 mismatches |
| Theorem 2b, 2c: probability, min cost | 400 trees | 0 error |
| Theorem 3: Shannon = enumeration | 400 DAGs | 1.0e-15 (tree formulas: 0.23) |
| Proposition 4: monotone design changes | 400 × 3 | 0 violations |

## 3. A metric for interaction: the gap

Suppose a reliability team and a security team each analyse the system correctly with their own
model, and a risk manager combines their answers properly, as independent risks:

```math
Q_{\text{separate}} = 1 - (1 - Q_{\text{phys}})(1 - Q_{\text{cyber}}).
```

What is missing? Take a small example: $\text{TOP} = (p_1 \wedge c_1) \vee p_2 \vee c_2$ with
physical events $p_1$ (0.1) and $p_2$ (0.01) and cyber steps $c_1$ (0.2) and $c_2$ (0.05):

* reliability team (no attacks): $Q_{\text{phys}} = 0.01$;
* security team (perfect hardware): $Q_{\text{cyber}} = 0.05$;
* combined: $Q_{\text{separate}} = 1 - 0.99 \times 0.95 = 0.0595$;
* unified: $Q = 1 - 0.98 \times 0.99 \times 0.95 = 0.07831$.

The difference, $\Gamma = 0.01881$, is 24 % of the risk. It is exactly the probability that the
mixed scenario $\{p_1, c_1\}$ happens while neither pure scenario does:
$0.02 \times 0.99 \times 0.95 = 0.01881$.

**Proposition 5** proves this holds for any model: $\Gamma$ equals the probability that the
consequence happens *only* through mixed scenarios, so it is never negative and is zero when
there are no mixed scenarios. The proof rests on one observation: "some physical-only cut set
has happened" depends only on physical events, "some cyber-only cut set has happened" only on
cyber events, so the two are independent, and both are sub-events of the top event.

In the case study, $\Gamma$ = 3.16e-4, **31 %** of the risk, all from the spoof that the
integrity monitor misses. The gap is a number a programme manager can understand: *this is
how much risk falls between the two teams*.

## 4. What the semantics cannot express

A static, coherent model has limits, and an honest methodology states them:

* **No order or time.** AND means "all within the window". "Gain access, *then* inject" and
  attack durations need dynamic gates (sequential AND, functional dependencies), as in
  attack-fault trees or BDMPs.
* **No negation, so no antagonism.** The classic example from the safety/security literature
  is a door that is locked against burglars but must open in a fire. "Unsafe" needs
  *locked* and "insecure" needs *not locked*. Without NOT, the model cannot represent one
  event helping one consequence and preventing another. Adding NOT would break coherence,
  and with it monotonicity (Proposition 4), the cut-set representation and the guarantee that
  every mitigation helps.
* **No adaptive adversary.** Steps are independent. A real attacker who fails at one step
  tries another.

These are the reasons to keep this model as a *front end* and an engineering tool, and to
hand questions about ordering, timing or antagonism to dynamic formalisms.

## 5. What is new, and what is not

[`related-work.md`](../related-work.md) compares the project with the formalisms in the most
complete recent survey (Nicoletti et al., arXiv:2106.06272, 2023). In short:

**Not new:** putting failures and attacks in one tree (Nai Fovino et al. did it in 2009;
attack-fault trees and BDMPs add dynamics); the Boolean semantics; cut sets; exact
quantification; importance measures; the beta factor; Pareto analysis of attack attributes
(attack-fault trees already do it).

**New, or new in combination, and worth testing in RES-02:**

1. RBDs as the input language, with a proved exact conversion. None of the fourteen surveyed
   formalisms starts from RBDs.
2. Proved and independently tested reductions to *both* classical models.
3. The **interaction gap**, a metric specific to safety/security interaction, which the
   survey lists as missing (its Finding #4).
4. Origin-preserving analyses (physical/cyber/mixed paths, the opportunistic front, two
   yardsticks for mitigation), which answer the survey's point that merged models lose the
   distinction between failure and attack.
5. A quantitative, validated embodiment of CCE's consequence-first workflow.

Each claim in the related-work note carries a strength rating. The interaction gap is the most
promising and the most in need of a systematic search before anyone calls it new. Claiming less
and being right is worth more than claiming more and being corrected by a reviewer.

---

## Exercises

1. Show that Theorem 1 fails if blocks are dependent, using two blocks that always fail
   together.
2. For $\text{TOP} = \text{AND}(c_1, \text{OR}(c_2, c_3))$, all cyber, list the attack
   scenarios by Definition 8 and check them against the cut sets.
3. Compute $\Gamma$ for $\text{TOP} = \text{AND}(p, c)$ with $P(p) = 0.1$, $P(c) = 0.3$. What
   share of the risk is it, and why?
4. Why does adding a NOT gate break Proposition 4? Give a two-event example.
5. A colleague says: "Your model is just a fault tree with coloured leaves." Write a
   three-sentence answer that is honest about what is old and precise about what is new.

### Solutions

1. Let blocks $a$ and $b$ be in parallel with $r = 0.9$ each, but always fail together. The
   true reliability is 0.9; the formula, which assumes independence, gives $1 - 0.01 = 0.99$.
   Theorem 1 assumes the independence of Definition 3. A shared cause has to be modelled
   explicitly, as a shared event or with the beta factor of Lesson 5.
2. $[\![\mathrm{OR}(c_2, c_3)]\!] = \{\{c_2\}, \{c_3\}\}$; the AND with $\{c_1\}$ gives
   $\{\{c_1, c_2\}, \{c_1, c_3\}\}$, which are the minimal cut sets.
3. $Q = 0.03$, $Q_{\text{phys}} = Q_{\text{cyber}} = 0$, so $\Gamma = 0.03$, 100 % of the risk.
   The only scenario is mixed: each team, analysing alone, would report zero risk.
4. With $\text{TOP} = \text{AND}(a, \text{NOT}\ b)$, raising $P(b)$ lowers $P(\text{TOP})$, so
   $Q$ is no longer non-decreasing in every input. "Making more things go wrong" can then
   make the consequence less likely, and a "mitigation" can increase risk.
5. For example: "The tree part is classical: fault and attack trees have been merged since
   2009, and the algorithms are textbook. What is new is that physical and cyber origins are
   kept through the analysis, with proofs that the model reduces exactly to the classical RBD
   and attack tree. That allows the interaction gap, the risk neither team's model contains, to
   be measured, and physical and cyber mitigations to be compared exactly on risk and on
   attacker effort."

## References

See [`formal-semantics.md`](../formal-semantics.md) and
[`related-work.md`](../related-work.md) for the full lists; the key sources are Mauw and
Oostdijk (2005), Nai Fovino, Masera and De Cian (2009), Kumar and Stoelinga (2017), Kriaa et
al. (2015), and Nicoletti, Peppelman, Kolb and Stoelinga (2023).
