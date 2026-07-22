from ffpolicy.core.presets import Preset, apply_preset, load_bundled_presets, load_preset
from ffpolicy.core.validator import validate_document
from ffpolicy.fetchers.schema_sync import load_bundled_schema
from ffpolicy.models.policy_document import PolicyDocument


def test_load_bundled_presets_includes_disa_stig():
    presets = load_bundled_presets()
    assert "disa_stig" in presets
    assert isinstance(presets["disa_stig"], Preset)


def test_load_preset_unknown_id_raises_key_error():
    try:
        load_preset("does-not-exist")
        raise AssertionError("expected KeyError")
    except KeyError as exc:
        assert "does-not-exist" in str(exc)
        assert "disa_stig" in str(exc)


def test_disa_stig_preset_has_expected_rule_counts():
    preset = load_preset("disa_stig")
    assert len(preset.rules) == 33
    assert len(preset.automated_rules) == 30
    assert len(preset.manual_rules) == 3
    manual_ids = {rule.id for rule in preset.manual_rules}
    assert manual_ids == {"V-251545", "V-251550", "V-251560"}


def test_apply_preset_sets_top_level_policies():
    document = PolicyDocument()
    apply_preset(document, load_preset("disa_stig"))

    assert document.values["DisableTelemetry"] is True
    assert document.values["SSLVersionMin"] == "tls1.2"
    assert document.values["ExtensionUpdate"] is False


def test_apply_preset_merges_multiple_rules_into_shared_preferences_key():
    """Several STIG rules (V-251547/548/554/555/569/570) each set a different
    sub-key of the Preferences policy - applying the preset must produce one
    Preferences dict with all of them, not have later rules clobber earlier ones.
    """
    document = PolicyDocument()
    apply_preset(document, load_preset("disa_stig"))

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
    apply_preset(document, load_preset("disa_stig"))

    tracking = document.values["EnableTrackingProtection"]
    assert tracking["Fingerprinting"] is True
    assert tracking["Cryptomining"] is True


def test_apply_preset_leaves_untouched_keys_alone():
    document = PolicyDocument(values={"Homepage": {"URL": "https://example.com"}})
    apply_preset(document, load_preset("disa_stig"))

    assert document.values["Homepage"] == {"URL": "https://example.com"}
    assert document.values["DisableTelemetry"] is True


def test_apply_preset_result_passes_validation_against_bundled_schema():
    document = PolicyDocument()
    apply_preset(document, load_preset("disa_stig"))

    schema = load_bundled_schema()
    issues = validate_document(document, policy_schema=schema, target_firefox_version=140)

    assert issues == []
