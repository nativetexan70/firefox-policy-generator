.PHONY: install lint typecheck test update-golden

install:
	pip install -e ".[dev]"

lint:
	ruff check src tests
	lint-imports

typecheck:
	mypy src

test:
	QT_QPA_PLATFORM=offscreen pytest --cov=ffpolicy

update-golden:
	python3 -c "\
import yaml; \
from pathlib import Path; \
from ffpolicy.core.generator import render_policies_json; \
from ffpolicy.models.policy_document import PolicyDocument; \
fixtures = Path('tests/fixtures'); \
data = yaml.safe_load((fixtures / 'sample_input.yaml').read_text()); \
document = PolicyDocument(values=data['policies']); \
(fixtures / 'golden' / 'sample_policies.json').write_text(render_policies_json(document))"
