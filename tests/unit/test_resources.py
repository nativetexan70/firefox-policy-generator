import importlib.resources
import json

import yaml

from ffpolicy.models.policy_schema import PolicySchema, ValueType


def _read_resource(name: str) -> str:
    return importlib.resources.files("ffpolicy.resources").joinpath(name).read_text()


def test_bundled_schema_backup_parses_as_policy_schema():
    data = json.loads(_read_resource("schema_backup.json"))
    schema = PolicySchema.model_validate(data)
    assert len(schema.policies) > 0
    assert "ExtensionSettings" in schema.policies


def test_ip_protection_available_policy_is_bundled():
    """IPProtectionAvailable (Firefox's built-in VPN) restricts access to the
    feature when disabled - added in Firefox 149.0.2/150.
    """
    data = json.loads(_read_resource("schema_backup.json"))
    schema = PolicySchema.model_validate(data)

    policy = schema.policies["IPProtectionAvailable"]
    assert policy.category == "Privacy & Network"
    assert policy.min_firefox_version == 150
    assert policy.root_field.type is ValueType.BOOL
    assert policy.root_field.default is True


def test_ai_controls_policy_is_bundled():
    """AIControls (Firefox 150+) grants/blocks AI features per-feature -
    Translations, PDFAltText, SmartTabGroups, LinkPreviewKeyPoints,
    SidebarChatbot (the AI chatbot), and SmartWindow - each with its own
    Value (available/blocked) and Locked, plus a Default that applies unless
    a feature overrides it.
    """
    data = json.loads(_read_resource("schema_backup.json"))
    schema = PolicySchema.model_validate(data)

    policy = schema.policies["AIControls"]
    assert policy.category == "AI Controls"
    assert policy.min_firefox_version == 150
    assert policy.root_field.type is ValueType.OBJECT

    children_by_key = {child.key: child for child in policy.root_field.children}
    assert set(children_by_key) == {
        "Default",
        "Translations",
        "PDFAltText",
        "SmartTabGroups",
        "LinkPreviewKeyPoints",
        "SidebarChatbot",
        "SmartWindow",
    }

    chatbot = children_by_key["SidebarChatbot"]
    assert chatbot.type is ValueType.OBJECT
    grandchildren = {gc.key: gc for gc in chatbot.children}
    assert grandchildren["Value"].type is ValueType.ENUM
    assert grandchildren["Value"].enum_values == ["available", "blocked"]
    assert grandchildren["Locked"].type is ValueType.BOOL


def test_generative_ai_policy_is_bundled():
    """GenerativeAI (Firefox 148+) is the simpler, all-in-one kill switch for
    generative AI features - Enabled turns everything off/on at once, with
    per-feature booleans and a Locked flag.
    """
    data = json.loads(_read_resource("schema_backup.json"))
    schema = PolicySchema.model_validate(data)

    policy = schema.policies["GenerativeAI"]
    assert policy.category == "AI Controls"
    assert policy.min_firefox_version == 148
    assert policy.root_field.type is ValueType.OBJECT

    children_by_key = {child.key: child for child in policy.root_field.children}
    assert set(children_by_key) == {
        "Enabled",
        "Chatbot",
        "LinkPreviews",
        "TabGroups",
        "SmartWindow",
        "Locked",
    }
    assert all(child.type is ValueType.BOOL for child in children_by_key.values())


def test_high_impact_policies_have_security_privacy_impact_text():
    data = json.loads(_read_resource("schema_backup.json"))
    schema = PolicySchema.model_validate(data)

    for name in ("ExtensionSettings", "DisableTelemetry", "SSLVersionMin", "Proxy"):
        impact = schema.policies[name].security_privacy_impact
        assert impact, f"{name} should document its security/privacy impact"
        assert len(impact) > 20


def test_purely_cosmetic_policies_have_no_security_privacy_impact_text():
    data = json.loads(_read_resource("schema_backup.json"))
    schema = PolicySchema.model_validate(data)

    for name in ("DisplayBookmarksToolbar", "Homepage", "FirefoxHome"):
        assert schema.policies[name].security_privacy_impact is None


def test_bundled_categories_yaml_is_valid_and_covers_known_policies():
    categories = yaml.safe_load(_read_resource("categories.yaml"))
    data = json.loads(_read_resource("schema_backup.json"))
    schema = PolicySchema.model_validate(data)

    known_names = set(schema.policies)
    listed_names = {name for names in categories.values() for name in names}

    assert known_names <= listed_names
