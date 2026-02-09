# Contributing to Galyarder Agent

Thanks for contributing.

## Scope

This repo is a monorepo:

- `backend/agent`: Python runtime (`g-agent`)
- `docs`: MkDocs documentation site source

## Local setup

### Backend

```bash
cd backend/agent
pip install -e ".[dev]"
ruff check g_agent tests --select F
pytest -q
```

### Docs

```bash
cd docs
python -m pip install -r requirements.txt
cd ..
mkdocs build --strict
```

### Optional: image asset compression

```bash
bash deploy/optimize-images.sh --dry-run
```

## Pull request rules

- Keep changes focused and minimal.
- Include tests/checks for behavior changes.
- Do not commit secrets or production tokens.
- Keep docs updated when behavior or setup changes.

## Safety and quality bar

- New features should keep default behavior safe.
- Breaking API/CLI changes must include migration notes.
- Security-sensitive changes should include a threat/risk note in the PR description.

## Reporting security issues

Please do not open public issues for vulnerabilities.
Use GitHub Security Advisories:

- https://github.com/galyarderlabs/galyarder-agent/security/advisories
