from ffpolicy.core.version_check import incompatibility_reason, is_compatible
from ffpolicy.models.policy_schema import PolicyDefinition, PolicyField, ValueType


def _definition(min_v=None, max_v=None):
    return PolicyDefinition(
        name="SomePolicy",
        root_field=PolicyField(key="SomePolicy", type=ValueType.BOOL),
        min_firefox_version=min_v,
        max_firefox_version=max_v,
    )


def test_no_bounds_is_always_compatible():
    assert is_compatible(_definition(), target_firefox_version=1) is True


def test_below_min_version_is_incompatible():
    d = _definition(min_v=100)
    assert is_compatible(d, target_firefox_version=99) is False
    assert "requires Firefox >= 100" in incompatibility_reason(d, 99)


def test_above_max_version_is_incompatible():
    d = _definition(max_v=100)
    assert is_compatible(d, target_firefox_version=101) is False
    assert "requires Firefox <= 100" in incompatibility_reason(d, 101)


def test_within_bounds_is_compatible():
    d = _definition(min_v=90, max_v=110)
    assert is_compatible(d, target_firefox_version=100) is True
    assert incompatibility_reason(d, 100) is None
