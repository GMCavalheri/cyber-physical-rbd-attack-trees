"""Hypothesis strategies shared by the tests: random RBDs and random unified models."""

from __future__ import annotations

from hypothesis import strategies as st

from cpsrbd.rbd import Block, KofN, Parallel, Rbd, Series
from cpsrbd.unified_graph_model import GateType, UnifiedModel, cyber_step, physical_event

probabilities = st.floats(0.01, 0.99)


@st.composite
def rbds(draw: st.DrawFn, depth: int = 3) -> Rbd:
    """Random nested series/parallel/k-of-n RBDs with distinct blocks."""
    counter = [0]

    def new_block() -> Block:
        counter[0] += 1
        return Block(f"b{counter[0]}", draw(probabilities))

    def build(d: int) -> Rbd:
        if d == 0 or draw(st.booleans()):
            return new_block()
        kids = tuple(build(d - 1) for _ in range(draw(st.integers(1, 3))))
        kind = draw(st.sampled_from(["series", "parallel", "kofn"]))
        if kind == "series":
            return Series(kids)
        if kind == "parallel":
            return Parallel(kids)
        return KofN(draw(st.integers(1, len(kids))), kids)

    return build(depth)


@st.composite
def models(
    draw: st.DrawFn,
    max_events: int = 8,
    max_gates: int = 6,
    tree: bool = False,
    origins: str = "mixed",
) -> UnifiedModel:
    """Random single-rooted DAGs (or trees) of AND/OR/KOFN gates over tagged events.

    Gates are created in order, each choosing children among the nodes created before it, so
    the graph is acyclic by construction. With ``tree=True`` a node is used at most once. The
    top gate collects every node that no gate has used yet, so all nodes are reachable.
    """
    n_events = draw(st.integers(2, max_events))
    m = UnifiedModel("top")
    for i in range(n_events):
        cyber = {"physical": False, "cyber": True}.get(origins, draw(st.booleans()))
        p = draw(probabilities)
        if cyber:
            m.add_event(cyber_step(f"e{i}", probability=p, cost=draw(st.integers(1, 20))))
        else:
            m.add_event(physical_event(f"e{i}", probability=p))
    nodes = [f"e{i}" for i in range(n_events)]
    unused = set(nodes)
    for j in range(draw(st.integers(0, max_gates))):
        pool = sorted(unused) if tree else nodes
        if len(pool) < 2:
            break
        children = draw(st.lists(st.sampled_from(pool), min_size=1, max_size=4, unique=True))
        kind = draw(st.sampled_from(list(GateType)))
        k = draw(st.integers(1, len(children))) if kind is GateType.KOFN else None
        name = f"g{j}"
        m.add_gate(name, kind, children, k=k)
        unused -= set(children)
        unused.add(name)
        nodes.append(name)
    kind = draw(st.sampled_from([GateType.AND, GateType.OR]))
    m.add_gate("top", kind, sorted(unused))
    return m.validate()
