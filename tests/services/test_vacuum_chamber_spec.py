import math
import random

from cadrecover.challenges.families import vacuum_chamber_spec as spec


def _seed(ports: int | None = None, bolts: int | None = None) -> int:
    return next(s for s in range(1000) if (ports is None or spec.port_count(spec.sample(s)) == ports)
                and (bolts is None or spec.bolt_count(spec.sample(s)) == bolts))


def test_sampling_is_deterministic_per_seed():
    assert spec.sample(42) == spec.sample(42)
    assert spec.sample(42) != spec.sample(43)


def test_samples_are_valid_and_drawing_friendly():
    ports, bolts = set(), set()
    for seed in range(300):
        p = spec.sample(seed)
        assert spec.is_valid(p), (seed, p)
        assert all((v * 2).is_integer() for v in p.values()), (seed, p)  # 0.5 mm steps
        ports.add(spec.port_count(p))
        bolts.add(spec.bolt_count(p))
    assert ports == {4, 5, 6} and bolts == {4, 6}


def test_validity_rules_reject_cramped_parts():
    p = spec.sample(_seed(6))
    assert spec.is_valid(p)
    lo, hi = spec.bolt_circle_bounds(p)
    assert not spec.is_valid(dict(p, port_bolt_circle_diameter=lo - 1.0))  # bolt holes into the stub
    assert not spec.is_valid(dict(p, port_bolt_circle_diameter=hi + 1.0))  # off the flange rim
    assert not spec.is_valid(dict(p, port_count=7.0)) and not spec.is_valid(dict(p, bolt_count=5.0))
    assert not spec.is_valid(dict(p, body_bore_diameter=p["body_diameter"] - 2.0))  # a 1 mm wall
    assert not spec.is_valid(dict(p, body_height=spec.stub_diameter(p) + 10.0))  # the stub would run off the body
    snug = dict(p, port_reach=150.0, body_diameter=200.0, body_bore_diameter=180.0, flange_thickness=10.0, port_diameter=25.0,
                flange_diameter=100.0, port_bolt_circle_diameter=70.0, port_bolt_hole_diameter=6.0, body_height=200.0)
    assert spec.is_valid(snug) and spec.is_valid(dict(snug, flange_diameter=125.0, port_count=4.0))
    assert not spec.is_valid(dict(snug, flange_diameter=125.0))  # flanges 45 degrees apart would collide
    assert not spec.is_valid({k: v for k, v in p.items() if k != "bolt_count"})
    assert not spec.is_valid(dict(p, port_reach=p["body_diameter"] / 2 + p["flange_thickness"] + 5.0))  # no stub left


def test_port_angles_follow_the_port_count():
    assert spec.port_angles({"port_count": 4.0}) == [0.0, 90.0, 180.0, 270.0]
    assert spec.port_angles({"port_count": 5.0}) == [0.0, 45.0, 90.0, 180.0, 270.0]
    assert spec.port_angles({"port_count": 6.0}) == [0.0, 45.0, 90.0, 135.0, 180.0, 270.0]


def test_port_features_sit_on_the_flange_face_with_outward_axes():
    for seed in range(40):
        p = spec.sample(seed)
        feats = spec.port_features(p)
        ports = [f for f in feats if f["kind"] == "port"]
        bolts = [f for f in feats if f["kind"] == "hole"]
        assert len(ports) == spec.port_count(p) and len(bolts) == spec.port_count(p) * spec.bolt_count(p)
        assert ports[0]["center"] == (p["port_reach"], 0.0, p["body_height"] / 2)  # port 1 on +X, mid-height
        for f in ports:
            assert math.hypot(f["center"][0], f["center"][1]) < p["port_reach"] + 1e-9
            assert math.isclose(math.hypot(*f["axis"]), 1.0)
        for f in bolts:  # every bolt hole lies on the bolt circle around its port's axis, on the flange face
            port = next(q for q in ports if q["name"] == f["name"].split("_bolt_")[0])
            assert f["axis"] == port["axis"]
            d = [a - b for a, b in zip(f["center"], port["center"])]
            assert abs(sum(x * y for x, y in zip(d, f["axis"]))) < 1e-9
            assert math.isclose(math.sqrt(sum(x * x for x in d)), p["port_bolt_circle_diameter"] / 2, rel_tol=1e-9)
        first = next(f for f in bolts if f["name"] == "port_1_bolt_1")
        assert math.isclose(first["center"][2], p["body_height"] / 2 + p["port_bolt_circle_diameter"] / 2)  # hole 1 up


def test_public_specs_carry_names_and_ranges_but_no_values():
    p = spec.sample(_seed(5))
    specs = spec.parameter_specs(p)
    assert {s.name for s in specs} == set(p) - set(spec.STRUCTURAL)  # counts are read off the drawing
    for s in specs:
        assert set(s.model_dump()) == {"name", "description", "unit", "min", "max"}
        assert (s.min, s.max) == spec.RANGES[s.name]


def test_critical_features_cover_the_body_bore_every_port_and_every_bolt_hole():
    for seed in range(10):
        p = spec.sample(seed)
        feats = {c.name: c.kind for c in spec.critical_feature_specs(p)}
        assert feats.pop("body_bore") == "bore"
        ports = {n for n, k in feats.items() if k == "port"}
        assert ports == {f"port_{k}" for k in range(1, spec.port_count(p) + 1)}
        bolts = {n for n, k in feats.items() if k == "hole"}
        assert bolts == {f"{n}_bolt_{j}" for n in ports for j in range(1, spec.bolt_count(p) + 1)}


def test_required_labels_cover_the_drawn_dimensions():
    p = spec.sample(_seed(4, 6))
    labels = spec.required_labels(p)
    for want in (f"⌀{p['port_diameter']:g}", f"⌀{p['port_diameter'] + 8:g}", f"⌀{p['flange_diameter']:g}",
                 f"⌀{p['port_bolt_circle_diameter']:g}", f"⌀{p['port_bolt_hole_diameter']:g}", f"{p['port_reach']:g}",
                 f"{p['body_height']:g}",
                 f"6× ⌀{p['port_bolt_hole_diameter']:g} THRU EQ SP ON ⌀{p['port_bolt_circle_diameter']:g} BC"):
        assert want in labels, want


def test_edit_candidates_are_valid_and_keep_the_structure():
    rng = random.Random(0)
    for seed in range(15):
        base = spec.sample(seed)
        made = 0
        for _ in range(80):
            cand = spec.edit_candidate(base, rng)
            if cand is None:
                continue
            made += 1
            assert spec.is_valid(cand)
            assert cand["port_count"] == base["port_count"] and cand["bolt_count"] == base["bolt_count"]
            ov = spec.overrides(base, cand)
            assert not set(ov) & set(spec.STRUCTURAL)
            assert abs(ov["port_diameter"] - base["port_diameter"]) >= spec.MIN_PORT_CHANGE
            circle = cand["port_bolt_circle_diameter"]
            assert abs(circle - base["port_bolt_circle_diameter"]) >= spec.MIN_CIRCLE_CHANGE
            assert abs(circle - base["port_bolt_circle_diameter"] * cand["port_diameter"] / base["port_diameter"]) >= spec.MIN_CIRCLE_CHANGE
        assert made > 0, base


def test_max_feature_shift_ignores_motion_along_a_port_axis():
    p = spec.sample(_seed(4, 6))
    assert spec.max_feature_shift(p, dict(p, port_reach=p["port_reach"] + 10)) == 0.0  # flanges slide along their axes
    assert abs(spec.max_feature_shift(p, dict(p, port_bolt_circle_diameter=p["port_bolt_circle_diameter"] + 4)) - 2.0) < 1e-9
    assert abs(spec.max_feature_shift(p, dict(p, body_height=p["body_height"] + 10)) - 5.0) < 1e-9  # ports sit at half height


def test_ledger_waivers_leave_the_dimension_labels_enforced():
    assert all(w.split(":")[0] in {"bosses", "holes", "hole_patterns"} for w in spec.LEDGER_WAIVERS)
    assert len(spec.required_labels(spec.sample(0))) >= 11
