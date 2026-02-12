# Contributing

See the root contributing guide:

- [CONTRIBUTING.md](https://github.com/galyarderlabs/galyarder-agent/blob/main/CONTRIBUTING.md)
- [CLI Error Style](cli-error-style.md)

## Local validation checklist

```bash
# backend
cd backend/agent
ruff check g_agent tests --select F
pytest -q

# docs
cd ../..
python -m pip install -r docs/requirements.txt
python backend/agent/scripts/generate_cli_docs.py
mkdocs build --strict

# optional: compress oversized tracked images
bash deploy/optimize-images.sh --dry-run
```

## Recommended: enable local git hooks

```bash
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit .githooks/pre-push
```
