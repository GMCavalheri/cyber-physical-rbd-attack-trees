# Scope and modelling boundaries

This repository is a **methodology and software** project. Everything in it is meant to be safe
to publish, and these rules keep it that way.

## What is modelled

* **A synthetic system.** The case study (a navigation chain feeding a mission computer) is a
  generic, defense-*representative* architecture invented for this project. It does not
  describe any real platform, product, operator or programme, and none of its numbers come from
  one.
* **Physical failures** through constant failure rates and an exposure window. The rates are
  round, plausible assumptions stated row by row in
  [`case_study_parameters.csv`](../src/cpsrbd/data/case_study_parameters.csv).
* **Cyber attack steps at the effect level only.** A step says *what the attack does to the
  system* (navigation messages are falsified, the bus is flooded, a modified software load
  reaches the computer) and how likely and costly that is, using an explicitly illustrative
  scoring scale. It never says *how* to do it: no vulnerabilities, exploit procedures, tools,
  protocol details or configurations.

## Public sources only

* Idaho National Laboratory's Consequence-driven Cyber-Informed Engineering (CCE) and
  Cyber-Informed Engineering (CIE) publications, for the consequence-first structure of the
  analysis.
* MITRE ATT&CK for ICS, used only as a **vocabulary**: each cyber step carries the ID of the
  technique whose effect it represents, as listed on <https://attack.mitre.org/techniques/ics/>
  (checked 2026-11-14). The tests keep the list of IDs used in the case study.
* Textbooks and peer-reviewed papers on reliability, fault trees and attack trees, cited in the
  lessons and in [`related-work.md`](related-work.md).

## How to read the numbers

* Physical probabilities are as good as their rates, which are assumptions.
* Cyber likelihoods are **expert-judgement scores mapped to a probability band**. They support
  *relative* comparisons (which path is easiest, which mitigation helps most) and sensitivity
  analysis. They are not field statistics, and the top-event probability is not a forecast.
* Every result in [`validation/results/`](../validation/results/) is reproducible from the
  parameter table, so anyone can replace the assumptions with their own and rerun.

## Out of scope

* Real system data, classified or export-controlled information, or anything obtained under a
  non-disclosure agreement.
* Offensive tooling, exploit development, or guidance for attacking any system.
