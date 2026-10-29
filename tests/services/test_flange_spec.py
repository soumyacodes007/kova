import random

from cadrecover.challenges.families import flange_spec as spec


def _seed(hub: bool) -> int:
    return next(s for s in range(1000) if spec.has_hub(spec.sample(s)) == hub)


def test_sampling_is_deterministic_per_seed():
    assert spec.sample(42) == spec.sample(42)
    assert spec.sample(42) != spec.sample(43)


def test_samples_are_valid_and_drawing_friendly():
    hubs, counts = 0, set()
    for seed in range(500):
        p = spec.sample(seed)
        assert spec.is_valid(p), (seed, p)
        assert all((v * 2).is_integer() for v in p.values()), (seed, p)  # 0.5 mm steps
        hubs += spec.has_hub(p)
        counts.add(spec.bolt_count(p))
    assert 100 < hubs < 400  # the optional hub shows up, but not always
    assert counts == {4, 6, 8}


def test_validity_rules_reject_cramped_parts():
    p = spec.sample(_seed(hub=False))
    assert spec.is_valid(p)
    lo, hi = spec.bolt_circle_bounds(p)
    assert lo <= p["bolt_circle_diameter"] <= hi
    # bolt holes breaking into the bore, running off the rim, or out of range
    assert not spec.is_valid(dict(p, bolt_circle_diameter=lo - 1.0))
    assert not spec.is_valid(dict(p, bolt_circle_diameter=hi + 1.0))
    assert not spec.is_valid(dict(p, bolt_count=5.0))
    assert not spec.is_valid(dict(p, outer_diameter=p["outer_diameter"] * 3))
    # a hub needs both its parameters, a wall around the bore, and the bolt holes clear of it
    hub = spec.sample(_seed(hub=True))
    assert not spec.is_valid({k: v for k, v in hub.items() if k != "hub_height"})
    assert not spec.is_valid(dict(hub, hub_diameter=hub["bore_diameter"] + 2.0))
    lo, _ = spec.bolt_circle_bounds(hub)
    assert lo >= hub["hub_diameter"] + 2 * spec.MIN_WALL + hub["bolt_hole_diameter"]


def test_bolt_holes_are_evenly_spaced_on_the_circle():
    for seed in range(40):
        p = spec.sample(seed)
        centres = list(spec.bolt_centers(p).values())
        assert len(centres) == spec.bolt_count(p)
        assert centres[0] == (p["bolt_circle_diameter"] / 2, 0.0)  # hole 1 on +X
        radii = {round((x * x + y * y) ** 0.5, 9) for x, y in centres}
        assert radii == {round(p["bolt_circle_diameter"] / 2, 9)}


def test_public_specs_carry_names_and_ranges_but_no_values():
    p = spec.sample(_seed(hub=True))
    specs = spec.parameter_specs(p)
    assert {s.name for s in specs} == set(p) - {"bolt_count"}  # the count is read off the drawing
    for s in specs:
        assert set(s.model_dump()) == {"name", "description", "unit", "min", "max"}
        assert (s.min, s.max) == spec.RANGES[s.name]


def test_critical_features_cover_bore_and_every_bolt_hole():
    for seed in range(10):
        p = spec.sample(seed)
        feats = {c.name: c.kind for c in spec.critical_feature_specs(p)}
        assert feats.pop("bore") == "bore"
        assert set(feats) == {f"bolt_{k}" for k in range(1, spec.bolt_count(p) + 1)}
        assert set(feats.values()) == {"hole"}


def test_required_labels_cover_the_drawn_dimensions():
    p = spec.sample(_seed(hub=False))
    labels = spec.required_labels(p)
    assert f"⌀{p['outer_diameter']:g}" in labels and f"⌀{p['bolt_circle_diameter']:g}" in labels
    assert f"⌀{p['bore_diameter']:g}" in labels and f"⌀{p['bolt_hole_diameter']:g}" in labels
    assert len(spec.required_labels(spec.sample(_seed(hub=True)))) == len(labels) + 2


def test_edit_candidates_are_valid_and_keep_the_structure():
    rng = random.Random(0)
    for seed in range(20):
        base = spec.sample(seed)
        made = 0
        for _ in range(60):
            cand = spec.edit_candidate(base, rng)
            if cand is None:
                continue
            made += 1
            assert spec.is_valid(cand)
            assert cand["bolt_count"] == base["bolt_count"]  # structural
            assert spec.has_hub(cand) == spec.has_hub(base)
            assert "bolt_count" not in spec.overrides(base, cand)
            assert spec.overrides(base, cand)["outer_diameter"] != base["outer_diameter"]
            assert abs(cand["bolt_circle_diameter"] - base["bolt_circle_diameter"]) >= spec.MIN_CIRCLE_CHANGE
        assert made > 0, base


def test_max_feature_shift_is_the_bolt_circle_radius_change():
    p = spec.sample(_seed(hub=False))
    q = dict(p, bolt_circle_diameter=p["bolt_circle_diameter"] + 4.0)
    assert abs(spec.max_feature_shift(p, q) - 2.0) < 1e-9
    assert spec.max_feature_shift(p, dict(p, outer_diameter=p["outer_diameter"] + 10)) == 0.0
