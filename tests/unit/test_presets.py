from ffpolicy.core.presets import Preset, apply_preset, load_bundled_presets, load_preset
from ffpolicy.core.validator import validate_document
from ffpolicy.fetchers.schema_sync import load_bundled_schema
from ffpolicy.models.policy_document import PolicyDocument

# One representative profile preset - values/rules are identical across all
# nine DISA STIG profiles for this benchmark, so any one exercises the shared
# ruleset; only id/name/profile metadata differ between them.
DISA_STIG_SAMPLE_ID = "disa_stig__mac_1_classified"


def test_load_bundled_presets_expands_all_nine_profiles():
    presets = load_bundled_presets()
    expected_ids = {
        "disa_stig__mac_1_classified",
        "disa_stig__mac_1_public",
        "disa_stig__mac_1_sensitive",
        "disa_stig__mac_2_classified",
        "disa_stig__mac_2_public",
        "disa_stig__mac_2_sensitive",
        "disa_stig__mac_3_classified",
        "disa_stig__mac_3_public",
        "disa_stig__mac_3_sensitive",
    }
    assert expected_ids <= presets.keys()
    for preset_id in expected_ids:
        assert isinstance(presets[preset_id], Preset)


def test_profile_presets_share_family_and_have_distinct_titles():
    presets = load_bundled_presets()
    sample = presets[DISA_STIG_SAMPLE_ID]

    assert sample.family == "DISA STIG - Mozilla Firefox"
    assert sample.profile_id == "MAC-1_Classified"
    assert sample.profile_title == "I - Mission Critical Classified"
    assert sample.name == "DISA STIG - Mozilla Firefox (I - Mission Critical Classified)"

    other = presets["disa_stig__mac_3_sensitive"]
    assert other.family == sample.family
    assert other.profile_title == "III - Administrative Sensitive"
    assert other.values == sample.values
    assert other.rules == sample.rules


def test_load_preset_unknown_id_raises_key_error():
    try:
        load_preset("does-not-exist")
        raise AssertionError("expected KeyError")
    except KeyError as exc:
        assert "does-not-exist" in str(exc)
        assert DISA_STIG_SAMPLE_ID in str(exc)


def test_disa_stig_preset_has_expected_rule_counts():
    preset = load_preset(DISA_STIG_SAMPLE_ID)
    assert len(preset.rules) == 33
    assert len(preset.automated_rules) == 30
    assert len(preset.manual_rules) == 3
    manual_ids = {rule.id for rule in preset.manual_rules}
    assert manual_ids == {"V-251545", "V-251550", "V-251560"}


def test_rules_carry_description_and_recommendation():
    preset = load_preset(DISA_STIG_SAMPLE_ID)
    rule = next(r for r in preset.rules if r.id == "V-251546")

    assert "TLS 1.2" in rule.description
    assert rule.recommendation == 'Set SSLVersionMin to "tls1.2" (or "tls1.3").'

    # every rule has non-empty description/recommendation text
    for r in preset.rules:
        assert r.description.strip()
        assert r.recommendation.strip()


def test_apply_preset_sets_top_level_policies():
    document = PolicyDocument()
    apply_preset(document, load_preset(DISA_STIG_SAMPLE_ID))

    assert document.values["DisableTelemetry"] is True
    assert document.values["SSLVersionMin"] == "tls1.2"
    assert document.values["ExtensionUpdate"] is False


def test_apply_preset_merges_multiple_rules_into_shared_preferences_key():
    """Several STIG rules (V-251547/548/554/555/569/570) each set a different
    sub-key of the Preferences policy - applying the preset must produce one
    Preferences dict with all of them, not have later rules clobber earlier ones.
    """
    document = PolicyDocument()
    apply_preset(document, load_preset(DISA_STIG_SAMPLE_ID))

    prefs = document.values["Preferences"]
    assert prefs["security.default_personal_cert"] == {
        "Value": "Ask Every Time",
        "Status": "locked",
    }
    assert prefs["browser.search.update"] == {"Value": False, "Status": "locked"}
    assert prefs["dom.disable_window_move_resize"] == {"Value": True, "Status": "locked"}
    assert prefs["dom.disable_window_flip"] == {"Value": True, "Status": "locked"}
    assert prefs["browser.contentblocking.category"] == {"Value": "strict", "Status": "locked"}
    assert prefs["extensions.htmlaboutaddons.recommendations.enabled"] == {
        "Value": False,
        "Status": "locked",
    }


def test_apply_preset_merges_tracking_protection_rules():
    """V-251567 sets Fingerprinting and V-251568 sets Cryptomining on the same
    EnableTrackingProtection policy - both must survive in the final value.
    """
    document = PolicyDocument()
    apply_preset(document, load_preset(DISA_STIG_SAMPLE_ID))

    tracking = document.values["EnableTrackingProtection"]
    assert tracking["Fingerprinting"] is True
    assert tracking["Cryptomining"] is True


def test_apply_preset_leaves_untouched_keys_alone():
    document = PolicyDocument(values={"Homepage": {"URL": "https://example.com"}})
    apply_preset(document, load_preset(DISA_STIG_SAMPLE_ID))

    assert document.values["Homepage"] == {"URL": "https://example.com"}
    assert document.values["DisableTelemetry"] is True


def test_apply_preset_result_passes_validation_against_bundled_schema():
    document = PolicyDocument()
    apply_preset(document, load_preset(DISA_STIG_SAMPLE_ID))

    schema = load_bundled_schema()
    issues = validate_document(document, policy_schema=schema, target_firefox_version=140)

    assert issues == []
