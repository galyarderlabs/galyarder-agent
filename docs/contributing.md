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

## Maintainer release checklist

Before tagging a release (`vX.Y.Z`):

1. Update version metadata:
   - `backend/agent/pyproject.toml`
   - `backend/agent/g_agent/__init__.py`
   - `backend/agent/uv.lock`
2. Update release docs:
   - `CHANGELOG.md`
   - `docs/release-notes/vX.Y.Z.md` (must exist and be non-empty)
   - If release closes/changes roadmap commitments, update `docs/roadmap/openclaw-delta.md` status mapping
3. Run validation:

```bash
cd backend/agent
python -m compileall -q g_agent
ruff check g_agent tests --select F
pytest -q
```

4. Open PR, merge to `main`, then push tag:

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

Notes:

- CI blocks version-bump PRs without non-empty `docs/release-notes/vX.Y.Z.md`.
- Release workflow publishes GitHub release notes from that file.
