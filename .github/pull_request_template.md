## Summary

- what changed
- why it changed

## Scope

- [ ] backend/agent
- [ ] docs
- [ ] ci/cd

## Validation

Describe commands run and results.

```bash
# backend
cd backend/agent
ruff check g_agent tests --select F
pytest -q

# docs
python -m pip install -r docs/requirements.txt
mkdocs build --strict
```

## Safety Checklist

- [ ] No secrets/tokens committed
- [ ] Security-impacting changes reviewed
- [ ] Docs updated (if behavior/setup changed)
