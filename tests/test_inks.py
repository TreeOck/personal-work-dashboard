import inks

PAL = [i["id"] for i in inks.load_palette()]


def test_palette_has_12_unique_inks_and_fallback_last():
    assert len(PAL) == 12 and len(set(PAL)) == 12
    assert PAL[-1] == inks.FALLBACK


def test_existing_assignments_never_change():
    existing = {"b": {"ink": "momiji", "variant": 0}}
    out = inks.assign(["a", "b"], existing)
    assert out["b"] == {"ink": "momiji", "variant": 0}


def test_new_projects_get_next_unused_ink_in_sorted_order():
    existing = {"b": {"ink": PAL[0], "variant": 0}}
    out = inks.assign(["c", "a", "b"], existing)
    assert out["a"]["ink"] == PAL[1] and out["c"]["ink"] == PAL[2]


def test_fallback_ink_is_not_handed_out_until_others_are_used():
    out = inks.assign([f"p{i:02d}" for i in range(11)], {})
    assert inks.FALLBACK not in {v["ink"] for v in out.values()}


def test_overflow_reuses_inks_with_a_new_variant():
    names = [f"p{i:02d}" for i in range(13)]
    out = inks.assign(names, {})
    assert out["p11"] == {"ink": inks.FALLBACK, "variant": 0}
    assert out["p12"] == {"ink": PAL[0], "variant": 1}


def test_resolve_adds_name_and_hex():
    r = inks.resolve({"a": {"ink": "momiji", "variant": 0}})
    assert r["a"] == {"ink": "momiji", "name": "Momiji · autumn leaves", "hex": "#9a2a2a", "variant": 0}


def test_unknown_ink_in_existing_file_falls_back(capsys):
    r = inks.resolve({"a": {"ink": "no-such-ink", "variant": 0}})
    assert r["a"]["ink"] == inks.FALLBACK
