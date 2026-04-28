# Release Checklist

Before tagging and publishing a new release for Galyarder Agent, complete this checklist so release notes, docs, security posture, and runtime checks stay aligned with the actual code.

## 1. Backend Checks

- [ ] Backend compile check passes (`cd backend/agent && python -m compileall -q g_agent`).
- [ ] Fatal lint passes (`cd backend/agent && ruff check g_agent tests --select F`).
- [ ] Full backend tests pass (`cd backend/agent && uv run pytest -q`).
- [ ] Ensure database migrations (SQLite schema changes) are handled cleanly or documented in the release notes if manual intervention is needed.
- [ ] Validate core startup flows: `g-agent onboard` and `g-agent start`.

## 2. Bridge & Integration Checks

- [ ] Ensure WhatsApp bridge authentication (`bridgeToken`) functions correctly with a test payload.
- [ ] Validate Telegram bot webhook/polling connection.
- [ ] Validate browser automation (`BrowserSession`) initializes properly.

## 3. Security & Dependabot Review

- [ ] Review any new open GitHub Dependabot alerts or security advisories.
- [ ] Ensure sensitive data is not leaked in newly added logging or command output.
- [ ] Verify that default `tools.restrictToWorkspace` and `allowFrom` policies are enforced properly.
- [ ] Check `python-dotenv` and `litellm` dependency overrides in `pyproject.toml` are up to date and secure.

## 4. Documentation & Insights

- [ ] The `CHANGELOG.md` is fully updated with the new version number, date, and comprehensive list of changes.
- [ ] Run `g-agent status` and check `/insights` output to verify activity aggregation works as intended.
- [ ] Update `docs/install-matrix.md` if any platform requirements or paths have changed.
- [ ] Ensure the MkDocs build is successful without broken links (`mkdocs build --strict`).

## 5. Config Migration Notes

- [ ] Add explicit instructions to the release notes if users need to manually merge new payload objects into their existing `config.json`.
- [ ] Note any changes to environment variables or service paths (systemd/launchd).

## 6. Tag and Publish

- [ ] Merge the release branch to `main` through a pull request unless repository rules explicitly allow direct push.
- [ ] Create an annotated git tag matching the version (e.g., `v0.1.14`).
- [ ] Push tags: `git push origin v0.1.14`.
- [ ] Draft a GitHub Release using the `CHANGELOG.md` updates.
