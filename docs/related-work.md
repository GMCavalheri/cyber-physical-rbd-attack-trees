# Related work, and what is (and is not) new here

The RES-02 plan says its novelty claim is the highest-risk part of the paper and must be
checked against combined safety/security methods before any formal writing. This note is that
first check. Its main source is the most complete recent survey of model-based safety/security
co-analysis, **Nicoletti, Peppelman, Kolb and Stoelinga, "Model-based Joint Analysis of Safety
and Security: Survey and Identification of Gaps"** (arXiv:2106.06272, v3, October 2023), which
compares fourteen formalisms. Statements about other methods below are attributed to that
survey or to the original paper; the claims about this project are backed by the code and
[`formal-semantics.md`](formal-semantics.md).

This is a preliminary review, not the RES-02 literature review: a systematic search (including
work after 2023) is still required before submission.

## 1. The two parent traditions

* **Reliability block diagrams and fault trees.** Success-logic RBDs and failure-logic fault
  trees are dual descriptions of the same coherent structure function (Barlow and Proschan,
  1975; Rausand and Høyland, 2004; the *Fault Tree Handbook*, NUREG-0492, 1981). Quantification
  by minimal cut sets and binary decision diagrams (Rauzy, 1993) and importance measures
  (Birnbaum, 1969; Vesely et al., 1983) are mature.
* **Attack trees.** Introduced by Schneier (1999) and formalised by Mauw and Oostdijk (2005),
  with attribute domains for quantitative questions. The survey by Kordy, Piètre-Cambacédès and
  Schweitzer (*Computer Science Review*, 13–14, 2014) covers the DAG-based family of attack and
  defence models.

## 2. Combined safety/security formalisms

| formalism | how it combines safety and security | dynamics | analyses (per the survey) |
|---|---|---|---|
| FT/AT integration (Nai Fovino, Masera and De Cian, *RESS* 94(9), 2009) | attack trees refine fault-tree leaves | static | probability of the top event |
| Component fault trees with security (Steiner and Liggesmeyer, SAFECOMP 2016) | attacks added as a new basic-event type; failures and attacks merged freely | static | fault-tree analyses (cut sets, probability) |
| Attack-fault trees (Kumar and Stoelinga, HASE 2017) | dynamic attack trees and dynamic fault trees merged; attacker profiles | dynamic (SAND, FDEP, spares) | statistical model checking (UPPAAL): probability, time and cost; Pareto frontiers between attributes |
| BDMPs for safety and security (Bouissou and Bon, *RESS* 82(2), 2003; Kriaa et al., SAFECOMP 2014) | Markov processes on leaves, triggers between them | dynamic | mean time to success, probability of success, ranked success sequences |
| Attack tree bow-ties (Abdo et al., *Computers & Security* 72, 2018) | attack trees attached to the cause side of a bow-tie | static | minimal cut sets with a safety likelihood and a security likelihood |
| FACT graphs (Sabaliauskaite and Mathur, 2015) | fault trees, attack trees and countermeasures | triggers | probability (not demonstrated in the source) |
| State/event fault trees (Roth and Liggesmeyer, SAFECOMP 2013) | fault trees with Petri-net states | dynamic | dependability metrics via stochastic Petri nets |
| STPA-Sec / STPA-SafeSec (Young and Leveson, *CACM* 57(2), 2014; Friedberg et al., *JISA* 34, 2017) | systems-theoretic control-structure hazard analysis extended to security | qualitative | unsafe/insecure control actions, no probabilities |

Kriaa, Piètre-Cambacédès, Bouissou and Halgand (*RESS* 139, 2015) survey the industrial
control-system side and define the four interaction types (conditional dependency, mutual
reinforcement, antagonism, independence) that Nicoletti et al. use to compare expressiveness.

Two findings of the Nicoletti et al. survey matter most here:

* **Finding #2:** none of the formalisms introduces new modelling constructs for
  safety/security interaction; they merge existing ones. In its discussion of component fault
  trees, which merge failures and attacks freely, the survey notes that as a result "no
  interactions or trade offs between safety and security can be studied".
* **Finding #4:** no metrics specific to safety/security interaction have been proposed. The
  authors suggest studying trade-offs between safety and security, for example by Pareto
  analysis.

## 3. What this project does **not** claim

* **Combining failures and attacks in one tree.** Done since at least 2009 (FT/AT), with richer
  dynamics in attack-fault trees and BDMPs.
* **The static Boolean semantics, minimal cut sets, exact quantification, importance
  measures, attribute domains, the beta-factor model.** All classical; the code reimplements
  them so they can be validated and combined, and cites their sources.
* **Pareto trade-off analysis as such.** Attack-fault trees already compute Pareto frontiers
  between attack attributes, and attack tree bow-ties give separate safety and security
  likelihoods for cut sets.
* **Expressiveness.** This model is *less* expressive than attack-fault trees or BDMPs: it
  has no order, time, repair or negation, so it cannot express antagonism (the locked-door
  example). See section 7 of the formal semantics.

## 4. What this project does contribute

Each item is stated so it can be checked, and the last column says how strong the claim is
before a systematic review.

| contribution | where | strength of the novelty claim |
|---|---|---|
| **RBDs as an input language**, with an exact conversion proved for series, parallel, k-of-n and path-set structures (Theorem 1). Reliability engineers can keep their native diagrams. | `rbd/`, Theorem 1 | No formalism in the 14-method survey takes RBDs as input. Moderate: RBD/fault-tree duality is classical; using it as the front end of a safety/security model is the new step. |
| **Proved and tested reductions to both classical models** (Theorems 1 and 2), against an independent attack-tree implementation. | `attack_tree.py`, `reduction_checks.md` | The survey does not report such conservative-extension results for the tree-based combinations. Moderate. |
| **The interaction gap** $\Gamma$: the probability that the consequence happens only through mixed scenarios, so that separate reliability and attack-tree analyses miss it even when their results are combined correctly (Proposition 5). 31 % of the risk in the case study. | `origin_decomposition` | A metric specific to safety/security interaction, the gap named in Finding #4. Promising, but most in need of a systematic search before claiming it as new. |
| **Origin-preserving analyses:** physical/cyber/mixed cut sets; the opportunistic front (attacker cost against the probability of the physical preconditions); two yardsticks for mitigations (risk and exact attacker effort). | `critical_path_identification/`, `mitigation_tradeoff_analysis/` | Answers the merged-model limitation the survey notes for component fault trees. Partially anticipated by ATBT's two likelihoods and AFT Pareto frontiers; the combination with exact DAG computation is the contribution. |
| **Physical and cyber mitigation portfolios compared exactly**, with common-cause redundancy, engineering-out, and robustness under input uncertainty and changes of the likelihood scale. | Lesson 5, `mitigation.md` | Low novelty in method, useful as a demonstration: the best portfolio for risk and the best for attacker effort differ at every budget. |
| **A computable CCE workflow:** consequence first, top-down development that cannot leave a branch half-done, engineering-out as $Q(0_i)$ and the new minimum attacker cost. | `consequence_driven_analysis/`, Lesson 4 | CCE (INL; Bochman and Freeman, 2021) is qualitative and workshop-based; a validated quantitative embodiment is the practical contribution. |
| **Open, tested software**: 99 % coverage, property tests of every theorem, seeded reproducible results. | the repository | Practical, not methodological. |

## 5. What RES-02 still needs

1. A systematic literature search (Scopus, IEEE Xplore, ACM DL, arXiv; 2009 to now) for
   "reliability block diagram" with attack/security, for metrics of safety/security
   interaction, and for quantitative CCE/CIE tooling, so the claims in section 4 can be
   confirmed or narrowed.
2. Model the survey's running example (the locked-door example) and its pipeline case study,
   if their parameters are published, to compare like for like, and state plainly where the
   static semantics falls short (antagonism).
3. A comparison table against attack-fault trees on one shared example: same structure, same
   numbers, results from both tools.

## References

* H. Abdo, M. Kaouk, J.-M. Flaus and F. Masse, "A safety/security risk analysis approach of
  industrial control systems: a cyber bowtie — combining new version of attack tree with bowtie
  analysis", *Computers & Security*, 72, 2018, pp. 175–195.
* R. E. Barlow and F. Proschan, *Statistical Theory of Reliability and Life Testing*, 1975.
* A. A. Bochman and S. Freeman, *Countering Cyber Sabotage: Introducing Consequence-Driven,
  Cyber-Informed Engineering (CCE)*, CRC Press, 2021.
* M. Bouissou and J.-L. Bon, "A new formalism that combines advantages of fault-trees and
  Markov models: Boolean logic driven Markov processes", *RESS*, 82(2), 2003, pp. 149–163.
* I. Friedberg, K. McLaughlin, P. Smith, D. Laverty and S. Sezer, "STPA-SafeSec: safety and
  security analysis for cyber-physical systems", *Journal of Information Security and
  Applications*, 34, 2017, pp. 183–196.
* B. Kordy, L. Piètre-Cambacédès and P. Schweitzer, "DAG-based attack and defense modeling:
  don't miss the forest for the attack trees", *Computer Science Review*, 13–14, 2014.
* S. Kriaa, M. Bouissou, F. Colin, Y. Halgand and L. Piètre-Cambacédès, "Safety and security
  interactions modeling using the BDMP formalism: case study of a pipeline", SAFECOMP 2014,
  pp. 326–341.
* S. Kriaa, L. Piètre-Cambacédès, M. Bouissou and Y. Halgand, "A survey of approaches
  combining safety and security for industrial control systems", *RESS*, 139, 2015,
  pp. 156–178.
* R. Kumar and M. Stoelinga, "Quantitative security and safety analysis with attack-fault
  trees", 18th IEEE International Symposium on High Assurance Systems Engineering (HASE), 2017,
  pp. 25–32.
* S. Mauw and M. Oostdijk, "Foundations of attack trees", ICISC 2005, LNCS 3935, 2006.
* I. Nai Fovino, M. Masera and A. De Cian, "Integrating cyber attacks within fault trees",
  *RESS*, 94(9), 2009, pp. 1394–1402.
* S. M. Nicoletti, M. Peppelman, C. Kolb and M. Stoelinga, "Model-based joint analysis of
  safety and security: survey and identification of gaps", arXiv:2106.06272 (v3, 2023).
* A. Rauzy, "New algorithms for fault trees analysis", *RESS*, 40(3), 1993.
* M. Roth and P. Liggesmeyer, "Modeling and analysis of safety-critical cyber physical systems
  using state/event fault trees", SAFECOMP 2013.
* G. Sabaliauskaite and A. P. Mathur, "Aligning cyber-physical system safety and security",
  *Complex Systems Design & Management Asia*, Springer, 2015, pp. 41–53.
* B. Schneier, "Attack trees", *Dr. Dobb's Journal*, 24(12), 1999.
* M. Steiner and P. Liggesmeyer, "Combination of safety and security analysis — finding
  security problems that threaten the safety of a system", SAFECOMP 2016.
* W. Young and N. G. Leveson, "An integrated approach to safety and security based on systems
  theory", *Communications of the ACM*, 57(2), 2014, pp. 31–35.
