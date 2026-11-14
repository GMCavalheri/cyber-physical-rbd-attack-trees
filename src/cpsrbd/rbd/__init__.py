r"""Classical reliability block diagrams (success logic) and their conversion to the unified model.

An RBD describes which components must *work* for the system to work:

* a **series** structure works only if every block works,
* a **parallel** structure works if at least one block works,
* a **k-out-of-n** structure works if at least k of its n blocks work,
* a general structure (e.g. the bridge) is given by its **minimal path sets**: the system works
  if every component of at least one path set works.

For independent blocks with reliabilities :math:`R_i` the closed forms are

.. math::

    R_\text{series} = \prod_i R_i, \qquad
    R_\text{parallel} = 1 - \prod_i (1 - R_i), \qquad
    R_{k/n} = \sum_{j=k}^{n} \binom{n}{j} R^j (1-R)^{n-j}\ \text{(identical blocks)}.

The unified model is written in failure logic, so :func:`to_unified` converts by duality
(De Morgan): "series works" becomes "OR of failures", "parallel works" becomes "AND of
failures", and "k of n work" becomes "at least n − k + 1 of n fail". The conversion is exact;
Phase 3 checks that propagating probabilities through the converted model returns
``1 - reliability(rbd)`` to machine precision.

This module replaces the RBD code that the plan expected to reuse from the "Avionics
Electronics Reliability" project, which has not been built.
"""

from cpsrbd.rbd.diagram import (
    Block,
    KofN,
    Parallel,
    PathSets,
    Rbd,
    Series,
    at_least_k,
    block,
    block_names,
    bridge,
    bridge_reliability,
    k_out_of_n_identical,
    reliability,
    to_unified,
    works,
)

__all__ = [
    "Block",
    "KofN",
    "Parallel",
    "PathSets",
    "Rbd",
    "Series",
    "block",
    "bridge",
    "at_least_k",
    "block_names",
    "bridge_reliability",
    "k_out_of_n_identical",
    "reliability",
    "to_unified",
    "works",
]
