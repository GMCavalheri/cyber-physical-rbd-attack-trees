"""Matplotlib drawings of unified models (no Graphviz needed).

The layout is layered: a node's layer is its longest distance from the top event, so every
edge points downward, and nodes in a layer are ordered by barycentre sweeps, which keeps most
edges from crossing on small models.

Gates are drawn as rounded boxes labelled AND / OR / k/n, physical events as circles and cyber
steps as diamonds; ``highlight`` draws a set of nodes (e.g. a critical cut set and the gates it
triggers) in a strong colour.
"""

from __future__ import annotations

from collections.abc import Collection

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from cpsrbd.unified_graph_model import GateType, Origin, UnifiedModel

PHYSICAL_COLOR = "#2f6db5"
CYBER_COLOR = "#c8452c"
GATE_COLOR = "#555555"
HIGHLIGHT_COLOR = "#e0a100"


def use_style() -> None:
    """A clean, consistent style for every figure in the repository."""
    plt.rcParams.update(
        {
            "figure.dpi": 110,
            "savefig.dpi": 150,
            "savefig.bbox": "tight",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.3,
            "font.size": 10,
        }
    )


def layered_layout(model: UnifiedModel, sweeps: int = 4) -> dict[str, tuple[float, float]]:
    """Positions (x, y) with the top event at y = 0 and layers at y = -1, -2, ...

    Layers start in depth-first (child) order and are then reordered by a few alternating
    barycentre sweeps (down by the parents' positions, up by the children's), the classic
    Sugiyama heuristic for reducing edge crossings.
    """
    depth: dict[str, int] = {model.top: 0}
    for name in reversed(model.bottom_up()):  # parents before children
        for child in model.children(name):
            depth[child] = max(depth.get(child, 0), depth[name] + 1)
    preorder: dict[str, int] = {}

    def visit(name: str) -> None:
        if name in preorder:
            return
        preorder[name] = len(preorder)
        for child in model.children(name):
            visit(child)

    visit(model.top)
    layers: dict[int, list[str]] = {}
    for name in sorted(depth, key=preorder.__getitem__):
        layers.setdefault(depth[name], []).append(name)
    parents: dict[str, list[str]] = {}
    for name in depth:
        for child in model.children(name):
            parents.setdefault(child, []).append(name)

    def x_of() -> dict[str, float]:
        return {
            n: i - (len(nodes) - 1) / 2 for nodes in layers.values() for i, n in enumerate(nodes)
        }

    levels = sorted(layers)
    for _ in range(sweeps):
        for level in levels[1:]:
            x = x_of()
            layers[level].sort(key=lambda n: sum(x[q] for q in parents[n]) / len(parents[n]))
        for level in reversed(levels[:-1]):
            x = x_of()
            layers[level].sort(
                key=lambda n: (
                    sum(x[c] for c in model.children(n)) / len(model.children(n))
                    if model.children(n)
                    else x[n]
                )
            )
    x = x_of()
    return {n: (x[n], -float(depth[n])) for n in depth}


def _label(model: UnifiedModel, name: str) -> str:
    if name in model.gates:
        gate = model.gates[name]
        if gate.kind is GateType.KOFN:
            return f"{gate.k}/{len(gate.children)}"
        return str(gate.kind)
    return ""


def draw_model(
    model: UnifiedModel,
    ax: Axes | None = None,
    highlight: Collection[str] = (),
    title: str = "",
    label_width: int = 14,
) -> Figure:
    """Draw the model; return the figure."""
    if ax is None:
        _, ax = plt.subplots(figsize=(13, 7))
    fig = ax.get_figure()
    assert isinstance(fig, Figure)
    pos = layered_layout(model)
    hl = set(highlight)
    for parent in model.gates:
        if parent not in pos:
            continue
        for child in model.children(parent):
            on = parent in hl and child in hl
            (x0, y0), (x1, y1) = pos[parent], pos[child]
            ax.plot(
                [x0, x1],
                [y0, y1],
                color=HIGHLIGHT_COLOR if on else "#b0b0b0",
                lw=2.4 if on else 0.9,
                zorder=1,
            )
    for name, (x, y) in pos.items():
        on = name in hl
        edge = HIGHLIGHT_COLOR if on else "white"
        if name in model.gates:
            ax.scatter(x, y, s=650, marker="s", color=GATE_COLOR, edgecolors=edge, lw=2.5, zorder=2)
            ax.text(x, y, _label(model, name), color="white", ha="center", va="center", fontsize=7)
        else:
            event = model.events[name]
            cyber = event.origin is Origin.CYBER
            ax.scatter(
                x,
                y,
                s=420,
                marker="D" if cyber else "o",
                color=CYBER_COLOR if cyber else PHYSICAL_COLOR,
                edgecolors=edge,
                lw=2.5,
                zorder=2,
            )
        text = name.replace("_", " ")
        wrapped = "\n".join(_wrap(text, label_width))
        ax.text(x, y - 0.22, wrapped, ha="center", va="top", fontsize=6.5, zorder=3)
    ax.scatter([], [], marker="s", color=GATE_COLOR, label="gate")
    ax.scatter([], [], marker="o", color=PHYSICAL_COLOR, label="physical failure")
    ax.scatter([], [], marker="D", color=CYBER_COLOR, label="cyber attack step")
    ax.legend(loc="upper right", fontsize=8, frameon=False)
    ax.set_axis_off()
    if title:
        ax.set_title(title)
    return fig


def _wrap(text: str, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    lines.append(current)
    return lines
