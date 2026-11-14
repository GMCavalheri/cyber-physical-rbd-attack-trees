"""RES-02 groundwork: check every theorem of docs/formal-semantics.md on seeded random models.

The pytest suite checks the same statements with Hypothesis on each run; this script runs a
larger, seeded batch and records the worst case of each check in a results table that the
paper can cite.
"""

from __future__ import annotations

import itertools
import math
import random

from cpsrbd import attack_tree as at
from cpsrbd.critical_path_identification import describe, min_attacker_cost, minimal_cut_sets
from cpsrbd.critical_path_identification.cut_sets import PathKind
from cpsrbd.probability_likelihood_propagation import (
    MIN_COST,
    bottom_up_probability,
    enumerate_probability,
    evaluate,
    exact_probability,
    origin_decomposition,
)
from cpsrbd.rbd import Block, KofN, Parallel, Rbd, Series, reliability, to_unified
from cpsrbd.unified_graph_model import (
    Gate,
    GateType,
    UnifiedModel,
    cyber_step,
    physical_event,
)

from common import table, write_result

SEED = 2026
N = 400


def random_rbd(rng: random.Random, depth: int = 3) -> Rbd:
    counter = itertools.count()

    def build(d: int) -> Rbd:
        if d == 0 or rng.random() < 0.35:
            return Block(f"b{next(counter)}", rng.uniform(0.01, 0.99))
        kids = tuple(build(d - 1) for _ in range(rng.randint(1, 3)))
        kind = rng.choice(["series", "parallel", "kofn"])
        if kind == "series":
            return Series(kids)
        if kind == "parallel":
            return Parallel(kids)
        return KofN(rng.randint(1, len(kids)), kids)

    return build(depth)


def random_attack_tree(rng: random.Random, depth: int = 3) -> at.AttackTree:
    steps = itertools.count()
    gates = itertools.count()

    def build(d: int) -> at.AttackTree:
        if d == 0 or rng.random() < 0.35:
            return at.Step(f"s{next(steps)}", rng.uniform(0.01, 0.99), rng.randint(1, 20))
        kids = tuple(build(d - 1) for _ in range(rng.randint(1, 3)))
        cls = at.And if rng.random() < 0.5 else at.Or
        return cls(f"g{next(gates)}", kids)

    root = build(depth)
    return root if not isinstance(root, at.Step) else at.Or("root", (root,))


def random_dag(rng: random.Random, n_events: int = 8, n_gates: int = 6) -> UnifiedModel:
    m = UnifiedModel("top")
    for i in range(n_events):
        p = rng.uniform(0.01, 0.99)
        if rng.random() < 0.5:
            m.add_event(cyber_step(f"e{i}", probability=p, cost=rng.randint(1, 20)))
        else:
            m.add_event(physical_event(f"e{i}", probability=p))
    nodes = [f"e{i}" for i in range(n_events)]
    unused = set(nodes)
    for j in range(n_gates):
        kids = rng.sample(nodes, rng.randint(1, min(4, len(nodes))))
        kind = rng.choice(list(GateType))
        k = rng.randint(1, len(kids)) if kind is GateType.KOFN else None
        m.add_gate(f"g{j}", kind, kids, k=k)
        unused -= set(kids)
        unused.add(f"g{j}")
        nodes.append(f"g{j}")
    m.add_gate("top", rng.choice([GateType.AND, GateType.OR]), sorted(unused))
    return m.validate()


def with_extra_child(m: UnifiedModel, gate: str, p: float) -> UnifiedModel:
    g = m.gates[gate]
    out = m.copy()
    out.add_event(physical_event("extra", probability=p))
    return out.with_gate(Gate(g.name, g.kind, (*g.children, "extra"), g.k))


def gap_by_enumeration(m: UnifiedModel) -> float:
    pure = [c.events for c in describe(m) if c.kind is not PathKind.MIXED]
    events = m.basic_events()
    total = 0.0
    for states in itertools.product((False, True), repeat=len(events)):
        up = {e.name for e, s in zip(events, states, strict=True) if s}
        if m.structure_function({e.name: e.name in up for e in events}) and not any(
            c <= up for c in pure
        ):
            total += math.prod(
                e.probability if s else 1 - e.probability
                for e, s in zip(events, states, strict=True)
            )
    return total


def main() -> None:
    rng = random.Random(SEED)
    rows = []

    # Theorem 1: all-physical models reduce to the classical RBD.
    err = 0.0
    for _ in range(N):
        rbd = random_rbd(rng)
        err = max(err, abs(exact_probability(to_unified(rbd)) - (1 - reliability(rbd))))
    rows.append(["Thm 1", "all-physical: P(TOP) = 1 − R(RBD)", N, "max abs. error", err])

    # Theorem 2: all-cyber trees reduce to classical attack trees.
    sc_mismatch, p_err, c_err = 0, 0.0, 0.0
    for _ in range(N):
        tree = random_attack_tree(rng)
        m = at.to_unified(tree)
        sc_mismatch += set(minimal_cut_sets(m)) != at.scenarios(tree)
        p_err = max(p_err, abs(exact_probability(m) - at.probability(tree)))
        c_err = max(c_err, abs(min_attacker_cost(m) - at.min_cost(tree)))
    rows.append(
        ["Thm 2a", "all-cyber: minimal cut sets = attack scenarios", N, "mismatches", sc_mismatch]
    )
    rows.append(["Thm 2b", "all-cyber: P(TOP) = classical probability", N, "max abs. error", p_err])
    rows.append(
        ["Thm 2c", "all-cyber: min attacker cost = classical min cost", N, "max abs. error", c_err]
    )

    # Theorem 3: Shannon decomposition is exact on DAGs; bottom-up is not.
    s_err, naive_err, dags = 0.0, 0.0, 0
    for _ in range(N):
        m = random_dag(rng)
        enum = enumerate_probability(m)
        s_err = max(s_err, abs(exact_probability(m) - enum))
        if not m.is_tree():
            dags += 1
            naive_err = max(naive_err, abs(bottom_up_probability(m) - enum))
    rows.append(
        ["Thm 3", "exact (Shannon) = enumeration on random DAGs", N, "max abs. error", s_err]
    )
    rows.append(
        [
            "(contrast)",
            "bottom-up (tree formulas) on the DAGs among them",
            dags,
            "max abs. error",
            naive_err,
        ]
    )

    # Proposition 4: monotonicity (coherence).
    v_leaf = v_or = v_and = 0
    for _ in range(N):
        m = random_dag(rng)
        q = exact_probability(m)
        e = rng.choice(m.basic_events())
        v_leaf += exact_probability(m, {e.name: rng.uniform(e.probability, 1)}) < q - 1e-12
        ors = [g for g, x in m.gates.items() if x.kind is GateType.OR]
        ands = [g for g, x in m.gates.items() if x.kind is GateType.AND]
        if ors:
            v_or += exact_probability(with_extra_child(m, rng.choice(ors), 0.5)) < q - 1e-12
        if ands:
            v_and += exact_probability(with_extra_child(m, rng.choice(ands), 0.5)) > q + 1e-12
    rows.append(
        ["Prop 4a", "raising a leaf probability never lowers P(TOP)", N, "violations", v_leaf]
    )
    rows.append(["Prop 4b", "adding an OR alternative never lowers P(TOP)", N, "violations", v_or])
    rows.append(
        ["Prop 4c", "adding an AND requirement never raises P(TOP)", N, "violations", v_and]
    )

    # Proposition 5: the interaction gap is the probability of mixed-only scenarios.
    g_err, g_neg = 0.0, 0
    for _ in range(N):
        m = random_dag(rng)
        d = origin_decomposition(m)
        g_neg += d.gap < -1e-12
        g_err = max(g_err, abs(d.gap - gap_by_enumeration(m)))
    rows.append(["Prop 5", "gap = P(only mixed scenarios happen) ≥ 0", N, "max abs. error", g_err])
    rows.append(["Prop 5", "gap < 0", N, "violations", g_neg])

    # Proposition 6: exact min cost over cut sets vs bottom-up on DAGs.
    worse = 0
    for _ in range(N):
        m = random_dag(rng)
        exact = min_attacker_cost(m)
        bu = evaluate(m, MIN_COST)[m.top]
        worse += exact > bu + 1e-9
    rows.append(["Prop 6", "min over cut sets ≤ bottom-up min cost", N, "violations", worse])

    path = write_result(
        "reduction_checks",
        "RES-02 · Reduction and property checks on random models",
        [
            (
                f"Results ({N} random models per row, seed {SEED})",
                table(["statement", "check", "models", "metric", "worst case"], rows),
            )
        ],
    )
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
