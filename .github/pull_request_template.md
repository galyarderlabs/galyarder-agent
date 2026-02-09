## Summary

- what changed
- why it changed

## Scope

- [ ] backend/agent
- [ ] landingpages
- [ ] docs
- [ ] ci/cd

## Validation

Describe commands run and results.

```bash
# backend
cd backend/agent
ruff check g_agent tests --select F
pytest -q

# landingpages
cd landingpages
npm run lint
npm run typecheck
npm run build
```

## Safety Checklist

- [ ] No secrets/tokens committed
- [ ] Security-impacting changes reviewed
- [ ] Docs updated (if behavior/setup changed)
