import random

from cadrecover.challenges.families import wafer_chuck_spec as spec


def _seed(ring2: bool, mount: bool) -> int:
    return next(s for s in range(1000) if spec.has_ring2(spec.sample(s)) == ring2 and spec.has_mount(spec.sample(s)) == mount)


def test_sampling_is_deterministic_per_seed():
    assert spec.sample(42) == spec.sample(42)
    assert spec.sample(42) != spec.sample(43)


def test_samples_are_valid_and_drawing_friendly():
    variants, counts1, counts2 = set(), set(), set()
    for seed in range(500):
        p = spec.sample(seed)
        assert spec.is_valid(p), (seed, p)
        assert all((v * 2).is_integer() for v in p.values()), (seed, p)  # 0.5 mm steps
        assert spec.hole_count(p) <= spec.MAX_HOLES
        variants.add((spec.has_ring2(p), spec.has_mount(p)))
        counts1.add(spec.circles(p)[1].count)
        if spec.has_ring2(p):
            counts2.add(int(p["ring2_count"]))
    assert variants == {(a, b) for a in (False, True) for b in (False, True)}
    assert counts1 == set(spec.RING1_COUNTS) and counts2 == set(spec.RING2_COUNTS)


def test_validity_rules_reject_cramped_parts():
    p = spec.sample(_seed(ring2=True, mount=True))
    assert spec.is_valid(p)
    # a circle out of order or too close to its neighbour, off the rim, or out of range
    assert not spec.is_valid(dict(p, ring1_diameter=p["pin_circle_diameter"]))
    assert not spec.is_valid(dict(p, ring2_diameter=p["ring1_diameter"] + 1.0))
    assert not spec.is_valid(dict(p, mount_circle_diameter=p["plate_diameter"] - 2.0))
    assert not spec.is_valid(dict(p, plate_diameter=spec.RANGES["plate_diameter"][1] + 1))
    # a ring whose holes would touch each other
    assert not spec.is_valid(dict(p, vacuum_hole_diameter=5.0, ring1_diameter=spec.RANGES["ring1_diameter"][0],
                                  ring1_count=12.0))
    # structure: counts from the allowed sets, optional ring/mount need all their parameters
    assert not spec.is_valid(dict(p, ring1_count=7.0))
    assert not spec.is_valid({k: v for k, v in p.items() if k != "ring2_count"})
    assert not spec.is_valid({k: v for k, v in p.items() if k != "mount_hole_diameter"})


def test_walls_between_holes_and_the_rim_hold_for_every_sample():
    import math

    for seed in range(200):
        p = spec.sample(seed)
        centres, dia = spec.hole_centers(p), spec.hole_diameters(p)
        names = list(centres)
        for i, a in enumerate(names):
            assert math.hypot(*centres[a]) + dia[a] / 2 + spec.MIN_WALL <= p["plate_diameter"] / 2 + 1e-9, (seed, a)
            for b in names[i + 1:]:
                assert math.dist(centres[a], centres[b]) - (dia[a] + dia[b]) / 2 >= spec.MIN_WALL - 1e-9, (seed, a, b)


def test_holes_are_evenly_spaced_with_hole_1_on_plus_x():
    for seed in range(40):
        p = spec.sample(seed)
        centres = spec.hole_centers(p)
        assert len(centres) == spec.hole_count(p)
        for c in spec.circles(p):
            pts = [centres[f"{c.prefix}_{k}"] for k in range(1, c.count + 1)]
            assert pts[0] == (p[c.circle] / 2, 0.0)
            assert {round((x * x + y * y) ** 0.5, 9) for x, y in pts} == {round(p[c.circle] / 2, 9)}
        assert len([n for n in centres if n.startswith("pin_")]) == 3


def test_public_specs_carry_names_and_ranges_but_no_values_or_counts():
    p = spec.sample(_seed(ring2=True, mount=True))
    specs = spec.parameter_specs(p)
    assert {s.name for s in specs} == {k for k in p if not k.endswith("_count")}
    for s in specs:
        assert set(s.model_dump()) == {"name", "description", "unit", "min", "max"}
        assert (s.min, s.max) == spec.RANGES[s.name]


def test_critical_features_cover_every_hole():
    for seed in range(10):
        p = spec.sample(seed)
        feats = {c.name: c.kind for c in spec.critical_feature_specs(p)}
        assert set(feats) == set(spec.hole_centers(p))
        assert set(feats.values()) == {"hole"}
        assert all(c.size_tolerance_mm == 0.1 and c.position_tolerance_mm == 0.1 for c in spec.critical_feature_specs(p))


def test_required_labels_cover_the_drawn_dimensions():
    p = spec.sample(_seed(ring2=False, mount=False))
    labels = spec.required_labels(p)
    assert f"⌀{p['plate_diameter']:g}" in labels and f"{p['thickness']:g}" in labels
    assert f"⌀{p['ring1_diameter']:g}" in labels and f"⌀{p['pin_circle_diameter']:g}" in labels
    assert f"⌀{p['vacuum_hole_diameter']:g}" in labels and f"⌀{p['pin_hole_diameter']:g}" in labels
    full = spec.sample(_seed(ring2=True, mount=True))
    assert f"⌀{full['ring2_diameter']:g}" in spec.required_labels(full)
    assert f"⌀{full['mount_circle_diameter']:g}" in spec.required_labels(full)


def test_edit_candidates_are_valid_keep_the_structure_and_defeat_scaling():
    rng = random.Random(0)
    for seed in range(20):
        base = spec.sample(seed)
        made = 0
        for _ in range(80):
            cand = spec.edit_candidate(base, rng)
            if cand is None:
                continue
            made += 1
            assert spec.is_valid(cand)
            assert {k for k in cand if k.endswith("_count")} == {k for k in base if k.endswith("_count")}
            assert not any(k.endswith("_count") for k in spec.overrides(base, cand))
            assert spec.has_ring2(cand) == spec.has_ring2(base) and spec.has_mount(cand) == spec.has_mount(base)
            assert spec.overrides(base, cand)["plate_diameter"] != base["plate_diameter"]
            ratio = cand["plate_diameter"] / base["plate_diameter"]
            assert abs(cand["ring1_diameter"] - base["ring1_diameter"]) >= spec.MIN_CIRCLE_CHANGE  # not "ignore the edit"
            assert abs(cand["ring1_diameter"] - base["ring1_diameter"] * ratio) >= spec.MIN_CIRCLE_CHANGE  # not "scale"
        assert made > 0, base


def test_max_feature_shift_is_the_largest_circle_radius_change():
    p = spec.sample(_seed(ring2=False, mount=False))
    q = dict(p, ring1_diameter=p["ring1_diameter"] + 4.0)
    assert abs(spec.max_feature_shift(p, q) - 2.0) < 1e-9
    assert spec.max_feature_shift(p, dict(p, plate_diameter=p["plate_diameter"] + 10)) == 0.0
