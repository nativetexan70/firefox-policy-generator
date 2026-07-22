"""Golden-file discipline: canonical policies.json output must stay byte-identical
unless intentionally regenerated (see `make update-golden`).
"""

from pathlib import Path

import yaml

from ffpolicy.core.generator import render_policies_json
from ffpolicy.models.policy_document import PolicyDocument

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_sample_input_renders_to_golden_output():
    input_data = yaml.safe_load((FIXTURES / "sample_input.yaml").read_text())
    document = PolicyDocument(values=input_data["policies"])

    rendered = render_policies_json(document)
    golden = (FIXTURES / "golden" / "sample_policies.json").read_text()

    assert rendered == golden


def test_rendering_is_deterministic_across_runs():
    input_data = yaml.safe_load((FIXTURES / "sample_input.yaml").read_text())
    document = PolicyDocument(values=input_data["policies"])

    first = render_policies_json(document)
    second = render_policies_json(PolicyDocument(values=dict(input_data["policies"])))

    assert first == second
