# Sprint Workflow

Use this checklist for each project sprint.

## Before Editing

1. Restate the scope if the sprint has multiple user messages.
2. Check current git status.
3. Identify touched files.
4. Group related work into a meaningful sprint where practical, instead of uploading one or two small changes at a time.
5. Avoid unrelated refactors.
6. Do not commit until the maintainer explicitly asks.

## During Editing

- Follow existing patterns in `web_config.py`, `bms_monitor.py`, `bms_notify.py` and `templates/index.html`.
- Use `apply_patch` for manual edits.
- Keep changes ASCII unless the file already uses non-ASCII and the change needs it.
- Add tests for behavior changes.
- Keep user-facing wording plain and operational.
- Preserve read-only BMS behavior.

## Version And Docs

When a sprint changes user-facing behavior or is intended for release:

1. Bump `config.yaml` version.
2. Update README Current Version.
3. Add a top entry in `CHANGELOG.md`.
4. Add release notes if the sprint is release-worthy.
5. Update screenshots/docs when UI changes are visible.

If the sprint is only an internal fix, ask or infer whether to bump the version based on prior user direction.

## Final Response

Include:

- what changed
- files touched at a high level
- validation run
- anything not done or risky
- git commit comment whenever a GitHub commit/upload is required
- GitHub release/comment when asked

Keep it short and practical.

## Commit / Upload Preference

Prefer sprint-sized commits that tell a useful story. Avoid pushing tiny one-or-two-change commits unless:

- the maintainer asks for a quick hotfix
- the change is urgent
- the change must be isolated for safety
- the previous sprint has already been closed

When the maintainer asks to commit or upload to GitHub, provide the exact commit comment before or after the commit so it can be reused in GitHub/VS Code.
