r"""Illustrative likelihood scoring for cyber attack steps.

Physical failures have field data behind their rates; cyber attack steps do not. Following the
qualitative practice of risk assessment (score the attacker's required capability and the
opportunity the system offers, then map the score to a likelihood band), each cyber step gets
two scores on 1–5 scales:

* **capability required** — 1: commodity tools and skills, 5: nation-state resources;
* **opportunity** — 1: no realistic access path, 5: routinely exposed.

The combined score ``s = opportunity + (6 - capability_required)`` runs from 2 to 10 and is
mapped log-linearly onto the probability of success within the analysis window:

.. math::

    \log_{10} p(s) = \log_{10} p_\text{low}
        + (\log_{10} p_\text{high} - \log_{10} p_\text{low}) \frac{s - 2}{8},

with the default band ``[1e-4, 1e-1]``. The band and the formula are **assumptions** chosen to
make the scale explicit and easy to vary in sensitivity analysis; they are not calibrated to
incident statistics, and results must be read as relative, not absolute.
"""

from __future__ import annotations

import math

SCALE = range(1, 6)
DEFAULT_BAND = (1e-4, 1e-1)


def combined_score(capability_required: int, opportunity: int) -> int:
    """``opportunity + (6 - capability_required)``, in 2..10."""
    if capability_required not in SCALE or opportunity not in SCALE:
        raise ValueError("scores must be integers on the 1-5 scale")
    return opportunity + (6 - capability_required)


def likelihood_from_scores(
    capability_required: int,
    opportunity: int,
    band: tuple[float, float] = DEFAULT_BAND,
) -> float:
    """Map the two scores to a probability of success in the window (log-linear band)."""
    low, high = band
    if not 0.0 < low <= high <= 1.0:
        raise ValueError("band must satisfy 0 < low <= high <= 1")
    s = combined_score(capability_required, opportunity)
    log_low, log_high = math.log10(low), math.log10(high)
    return float(10.0 ** (log_low + (log_high - log_low) * (s - 2) / 8))
