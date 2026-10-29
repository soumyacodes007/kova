from cadrecover.challenges.families import plate_spec as spec


def test_sampling_is_deterministic_per_seed():
    assert spec.sample(42) == spec.sample(42)
    assert spec.sample(42) != spec.sample(43)


def test_samples_are_valid_and_drawing_friendly():
    slots = 0
    for seed in range(500):
        p = spec.sample(seed)
        assert spec.is_valid(p), (seed, p)
        assert all((v * 2).is_integer() for v in p.values()), (seed, p)  # 0.5 mm steps
        slots += spec.has_slot(p)
    assert 100 < slots < 400  # the optional slot actually shows up, but not always


def test_public_specs_carry_names_and_ranges_but_no_values():
    p = spec.sample(7)
    specs = spec.parameter_specs(p)
    assert {s.name for s in specs} == set(p)
    for s in specs:
        # only the published range; the drawn value must be read off the drawing
        assert set(s.model_dump()) == {"name", "description", "unit", "min", "max"}
        assert (s.min, s.max) == spec.RANGES[s.name]


def test_critical_features_cover_holes_and_slot():
    p = spec.sample(0)
    names = {c.name for c in spec.critical_feature_specs(p)}
    assert {"hole_1", "hole_2", "hole_3", "hole_4"} <= names
    assert ("slot" in names) == spec.has_slot(p)
