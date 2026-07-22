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


def test_bundled_categories_yaml_is_valid_and_covers_known_policies():
    categories = yaml.safe_load(_read_resource("categories.yaml"))
    data = json.loads(_read_resource("schema_backup.json"))
    schema = PolicySchema.model_validate(data)

    known_names = set(schema.policies)
    listed_names = {name for names in categories.values() for name in names}

    assert known_names <= listed_names
