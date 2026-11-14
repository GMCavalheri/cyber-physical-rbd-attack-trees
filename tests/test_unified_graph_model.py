import itertools
import math

import pytest

from cpsrbd.unified_graph_model import (
    BasicEvent,
    Gate,
    GateType,
    ModelError,
    Origin,
    UnifiedModel,
    cyber_step,
    physical_event,
    probability_from_rate,
)


def small_model() -> UnifiedModel:
    """Loss of a function fed by two redundant sensors, either of which an attacker can spoof,
    with a shared power supply."""
    m = UnifiedModel("top", "toy")
    m.add_events(
        [
            physical_event("sensor_a", probability=0.1),
            physical_event("sensor_b", probability=0.2),
            physical_event("power", probability=0.01),
            cyber_step("spoof", probability=0.05, cost=4.0, technique="T0856"),
        ]
    )
    m.and_("both_sensors", "sensor_a", "sensor_b")
    m.or_("top", "both_sensors", "power", "spoof")
    return m.validate()


def test_probability_from_rate_matches_exponential_law() -> None:
    # P(T <= t) = 1 - exp(-lambda t) for an exponential lifetime
    assert probability_from_rate(1e-4, 10.0) == pytest.approx(1 - math.exp(-1e-3), rel=1e-15)
    assert probability_from_rate(0.0, 5.0) == 0.0
    with pytest.raises(ValueError):
        probability_from_rate(-1.0, 1.0)


def test_physical_event_from_rate_records_its_inputs() -> None:
    e = physical_event("pump", failure_rate=2e-5, exposure_time=1000.0, source="assumed")
    assert e.origin is Origin.PHYSICAL
    assert e.cost == math.inf
    assert e.probability == pytest.approx(-math.expm1(-0.02))
    assert e.attributes == {"failure_rate": 2e-5, "exposure_time": 1000.0, "source": "assumed"}


@pytest.mark.parametrize(
    "kwargs",
    [{}, {"failure_rate": 1e-3}, {"probability": 0.1, "failure_rate": 1e-3}],
)
def test_physical_event_needs_exactly_one_parameterisation(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        physical_event("x", **kwargs)


def test_cyber_step_carries_scores_and_technique() -> None:
    e = cyber_step("inject", probability=0.02, cost=8, technique="T0830", capability=3.0)
    assert e.origin is Origin.CYBER
    assert e.attributes == {"capability": 3.0, "technique": "T0830"}


@pytest.mark.parametrize("p", [-0.1, 1.1, math.nan])
def test_basic_event_rejects_bad_probability(p: float) -> None:
    with pytest.raises(ValueError):
        BasicEvent("x", Origin.PHYSICAL, p)


def test_basic_event_rejects_negative_cost() -> None:
    with pytest.raises(ValueError):
        BasicEvent("x", Origin.CYBER, 0.5, -1.0)


def test_gate_thresholds() -> None:
    assert Gate("g", GateType.AND, ("a", "b", "c")).threshold() == 3
    assert Gate("g", GateType.OR, ("a", "b", "c")).threshold() == 1
    assert Gate("g", GateType.KOFN, ("a", "b", "c"), k=2).threshold() == 2


def test_queries_on_a_small_model() -> None:
    m = small_model()
    assert len(m) == 6
    assert "spoof" in m and "nope" not in m
    assert m.is_gate("top") and not m.is_gate("spoof")
    assert m.children("both_sensors") == ("sensor_a", "sensor_b")
    assert m.children("spoof") == ()
    assert [e.name for e in m.basic_events()] == ["power", "sensor_a", "sensor_b", "spoof"]
    assert m.origins() == {Origin.PHYSICAL, Origin.CYBER}
    assert m.is_tree() and m.shared_events() == []
    order = m.bottom_up()
    assert order[-1] == "top"
    assert order.index("sensor_a") < order.index("both_sensors")
    assert isinstance(m.node("top"), Gate) and isinstance(m.node("power"), BasicEvent)
    with pytest.raises(ModelError):
        m.node("nope")
    assert "cyber steps: 1" in repr(m)


def test_structure_function_is_the_boolean_logic() -> None:
    m = small_model()
    names = [e.name for e in m.basic_events()]
    for states in itertools.product((False, True), repeat=len(names)):
        s = dict(zip(names, states, strict=True))
        expected = (s["sensor_a"] and s["sensor_b"]) or s["power"] or s["spoof"]
        assert m.structure_function(s) is expected


def test_kofn_structure_function() -> None:
    m = UnifiedModel("vote")
    m.add_events(physical_event(n, probability=0.1) for n in "abc")
    m.kofn("vote", 2, "a", "b", "c").validate()
    for states in itertools.product((False, True), repeat=3):
        s = dict(zip("abc", states, strict=True))
        assert m.structure_function(s) is (sum(states) >= 2)


def test_shared_nodes_and_path_counts() -> None:
    # The bridge-like DAG: "power" feeds both channels.
    m = UnifiedModel("top")
    m.add_events(physical_event(n, probability=0.1) for n in ("a", "b", "power"))
    m.or_("chan_a", "a", "power").or_("chan_b", "b", "power").and_("top", "chan_a", "chan_b")
    m.validate()
    assert m.path_counts() == {"top": 1, "chan_a": 1, "chan_b": 1, "a": 1, "b": 1, "power": 2}
    assert m.shared_events() == ["power"]
    assert not m.is_tree()


def test_graph_export_has_attributes() -> None:
    g = small_model().graph()
    assert set(g.successors("top")) == {"both_sensors", "power", "spoof"}
    assert g.nodes["spoof"]["origin"] == "cyber"
    assert g.nodes["top"]["kind"] == "OR"


def test_copies_do_not_alias() -> None:
    m = small_model()
    m2 = m.with_event(physical_event("power", probability=0.5))
    assert m.events["power"].probability == 0.01
    assert m2.events["power"].probability == 0.5
    m3 = m.with_gate(Gate("top", GateType.OR, ("both_sensors", "power")))
    assert m3.children("top") == ("both_sensors", "power")
    with pytest.raises(ModelError):
        m3.validate()  # "spoof" is now unreachable
    m4 = m3.pruned().validate()
    assert "spoof" not in m4 and "spoof" in m
    m5 = m.with_gate(Gate("power", GateType.OR, ("sensor_a",)))
    assert m5.is_gate("power") and "power" not in m5.events
    with pytest.raises(ModelError):
        m.with_event(physical_event("missing", probability=0.1))
    with pytest.raises(ModelError):
        m.with_gate(Gate("missing", GateType.OR, ("power",)))


@pytest.mark.parametrize(
    ("build", "message"),
    [
        (lambda m: m, "top event"),
        (lambda m: m.or_("top", "ghost"), "undefined node"),
        (lambda m: m.add_gate("top", GateType.OR, []), "no children"),
        (lambda m: m.or_("top", "a", "a"), "twice"),
        (lambda m: m.kofn("top", 3, "a", "b"), "k = 3"),
        (lambda m: m.add_gate("top", GateType.AND, ["a"], k=1), "only meaningful"),
        (lambda m: m.or_("top", "g").or_("g", "top"), "cycle"),
        (lambda m: m.or_("top", "a").or_("orphan", "b"), "not reachable"),
    ],
)
def test_validation_errors(build, message: str) -> None:  # type: ignore[no-untyped-def]
    m = UnifiedModel("top")
    m.add_events(physical_event(n, probability=0.1) for n in ("a", "b"))
    with pytest.raises(ModelError, match=message):
        build(m).validate()


def test_duplicate_and_empty_names_are_rejected() -> None:
    m = UnifiedModel("top")
    m.add_event(physical_event("a", probability=0.1))
    with pytest.raises(ModelError):
        m.add_event(physical_event("a", probability=0.2))
    with pytest.raises(ModelError):
        m.or_("a", "a")
    with pytest.raises(ModelError):
        m.add_event(physical_event("", probability=0.2))
