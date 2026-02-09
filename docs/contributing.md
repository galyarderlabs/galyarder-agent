# Contributing

See the root contributing guide:

- [CONTRIBUTING.md](https://github.com/galyarderlabs/galyarder-agent/blob/main/CONTRIBUTING.md)

## Local validation checklist

```bash
# backend
cd backend/agent
ruff check g_agent tests --select F
pytest -q

# docs
cd ../..
python -m pip install -r docs/requirements.txt
mkdocs build --strict

# optional: compress oversized tracked images
bash deploy/optimize-images.sh --dry-run
```
