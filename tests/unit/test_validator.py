from ffpolicy.core.validator import IssueLevel, has_errors, validate_document
from ffpolicy.models.policy_document import PolicyDocument


def test_valid_document_has_no_issues():
    doc = PolicyDocument(values={"DisableTelemetry": True})
    assert validate_document(doc) == []


def test_force_installed_requires_install_url():
    doc = PolicyDocument(
        values={"ExtensionSettings": {"ext@example.com": {"installation_mode": "force_installed"}}}
    )
    issues = validate_document(doc)
    assert has_errors(issues)
    assert any("requires install_url" in i.message for i in issues)


def test_blocked_must_not_set_install_url():
    doc = PolicyDocument(
        values={
            "ExtensionSettings": {
                "ext@example.com": {
                    "installation_mode": "blocked",
                    "install_url": "https://example.com/x.xpi",
                }
            }
        }
    )
    issues = validate_document(doc)
    assert has_errors(issues)
    assert any("must not set install_url" in i.message for i in issues)


def test_allowed_and_force_installed_are_valid():
    doc = PolicyDocument(
        values={
            "ExtensionSettings": {
                "a@example.com": {"installation_mode": "allowed"},
                "b@example.com": {
                    "installation_mode": "force_installed",
                    "install_url": "https://example.com/b.xpi",
                },
            }
        }
    )
    assert validate_document(doc) == []


def test_unknown_installation_mode_is_an_error():
    doc = PolicyDocument(
        values={"ExtensionSettings": {"ext@example.com": {"installation_mode": "bogus"}}}
    )
    issues = validate_document(doc)
    assert has_errors(issues)
    assert issues[0].level is IssueLevel.ERROR
