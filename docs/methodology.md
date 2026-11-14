# Methodology: a computable CCE analysis

This project takes the structure of Idaho National Laboratory's **Consequence-driven
Cyber-Informed Engineering (CCE)** and turns it into a model that can be computed, validated and
compared across options. CCE is the inspiration and the skeleton; the reliability-engineering
tools (RBDs, fault-tree quantification, importance measures, common-cause models) are the
muscle. This note maps the two, step by step, and states the limits.

## 1. CCE in one paragraph

CCE starts from the premise that a capable, targeted adversary will get into the networks, and
asks what they could then make the physical process do. It runs in four phases: **consequence
prioritization** (choose the high-consequence events that must never happen), **system-of-systems
analysis** (map what the function behind each event depends on), **consequence-based targeting**
(work out what an adversary would need to do, step by step, to cause it), and **mitigations and
protections**, with a preference for engineering changes that remove the digital path to the
physical effect (INL; Bochman and Freeman, 2021). It is usually run as facilitated workshops,
and its outputs are qualitative.

## 2. Phase by phase

| CCE phase | what the analyst does here | code | output |
|---|---|---|---|
| 1 · Consequence prioritization | state the consequence as a function, how it is lost (availability **and** integrity), and a window | `Consequence`, `ConsequenceBuilder` | the top event |
| 2 · System-of-systems analysis | develop the consequence top-down into functions and dependencies; author redundant hardware as RBDs and convert exactly | `ConsequenceBuilder.any_of/all_of/at_least`, `rbd.to_unified` | gates, shared dependencies, physical-only branches |
| 3 · Consequence-based targeting | add effect-level attack steps where an adversary could remove a dependency; score them; find the paths | `cyber_step`, `likelihood_from_scores`, `minimal_cut_sets`, `cheapest_attacks`, `opportunistic_front` | cyber and mixed branches, the cheapest attack, the paths that combine an attack with a failure |
| 4 · Mitigations and protections | express each option as a model change; compare singly and in portfolios on risk and attacker effort; prefer engineering-out where it pays | `AddRedundancy`, `ReduceProbability`, `RequireStep`, `EngineerOut`, `assess`, `portfolios`, `pareto_front` | ranked options, Pareto fronts, budget choices |

Two cross-cutting checks run at every phase: `validate()` (the model is well formed) and the
origin views (what a reliability-only or attack-tree-only analysis would see, and the
**interaction gap** between them).

## 3. The workflow on the case study

1. **Consequence:** *the mission computer loses trustworthy navigation data during the
   mission* (10 h). Integrity is included, because a system that trusts false data can be
   worse off than one that knows it has none.
2. **System of systems:** two navigation units in 1-out-of-2 redundancy, a dual-channel bus, a
   mission computer fed from two power buses. Shared dependencies: the power buses, and (on
   the cyber side) any foothold on the bus. 15 gates in total.
3. **Targeting:** seven effect-level steps, each tagged with the ATT&CK for ICS technique whose
   effect it represents. Cut-set analysis finds 12 minimal paths. The cheapest attacker-controlled
   one costs 5 analyst-weeks (compromised maintenance laptop + bus flooding). The most likely
   overall is a physical single point of failure (the mission computer). A mixed path, a GNSS
   spoof that the integrity cross-check misses, carries 31 % of the risk, and that 31 % is
   exactly the interaction gap: neither team's model contains it.
4. **Mitigations:** eight costed options. The redundant computer removes the most risk;
   laptop hardening gives the most per unit invested; only engineering out the laptop (an
   offline software loader) raises the cheapest attack from 5 to 42 weeks. The best portfolio
   for risk and the best for attacker effort differ at every budget above 100 units, and the
   ranking moves with the assumed cyber likelihood scale. Both are shown, not hidden.

The numbers are in [`validation/results/`](../validation/results/) and are reproduced by
`validation/run_all.py` in CI.

## 4. What the computation adds to CCE

* **Exactness on shared dependencies.** Workshop reasoning tends to treat redundant channels as
  independent; the model does not, and Lesson 3 shows how wrong the independent answer can be.
* **One currency for physical and cyber options.** Redundancy, detection, hardening,
  authentication and engineering-out all become model changes evaluated the same way.
* **Two yardsticks, made explicit.** Probability (random failures, opportunistic attack) and
  minimum attacker effort (targeted attack, CCE's premise) can disagree; the model shows by how
  much and where.
* **Sensitivity as a habit.** Because the cyber inputs are judgements, every conclusion is
  rerun under input uncertainty and under a different likelihood scale, and only the robust
  ones are kept.

## 5. Limits, stated plainly

* **Cyber likelihoods are expert judgement.** They come from an explicit, illustrative scoring
  band, not from incident statistics. The model supports comparison and sensitivity analysis,
  not forecasts of how often a consequence will occur.
* **The value is structural, not predictive precision.** The firm results are structural
  (which paths exist, which are mixed, what an engineer-out removes, which options dominate
  which); the absolute probabilities carry an uncertainty of an order of magnitude or more.
* **Static semantics.** No order, timing, repair or adaptive adversary, and no negation, so no
  antagonistic interactions ([formal semantics, §7](formal-semantics.md)). Dynamic formalisms
  (attack-fault trees, BDMPs) are the tools for those questions.
* **Independence.** Basic events are independent; known dependence must be modelled
  explicitly (shared events, beta factors).
* **Synthetic case study.** The system and all parameters are invented and public by design
  ([scope](scope.md)); the case study demonstrates the method and is not an assessment of any
  real system.

## References

* Idaho National Laboratory, *Consequence-driven Cyber-informed Engineering (CCE)*,
  <https://inl.gov/national-security/cce/>, and the *CCE Phase 1–4 Reference Document*, 2023.
* A. A. Bochman and S. Freeman, *Countering Cyber Sabotage: Introducing Consequence-Driven,
  Cyber-Informed Engineering (CCE)*, CRC Press, 2021.
* U.S. Department of Energy, *National Cyber-Informed Engineering Strategy*, June 2022.
