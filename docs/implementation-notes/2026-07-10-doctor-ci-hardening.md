# Implementation Notes: GitHub Issues #4 and #9

## Plan Reference

- GitHub Issue [#4](https://github.com/House-lovers7/agent-session-control-stack/issues/4)
- GitHub Issue [#9](https://github.com/House-lovers7/agent-session-control-stack/issues/9)
- ACOS run `20260710T060203Z-Fix-GitHub-issues-4-and-9-harden-ascs-do`

## Decisions

- Use `claude plugin list --json` as the supported source for effective plugin enablement. Any command, timeout, size, JSON, or schema failure becomes `UNKNOWN`.
- Run one standard-library Python helper with `python3 -I`; keep the shell launcher minimal and exclude project-controlled Python startup hooks.
- Treat a loopback TCP connection as port availability only. The doctor never claims that the listener is pxpipe without an identity protocol.
- Parse and redact `ANTHROPIC_BASE_URL`; never echo the environment value verbatim.
- Resolve known `statusLine` deep-merge precedence, additive hook producers, managed drop-ins, and `disableAllHooks` across user, project, project-local, and file-managed settings. Stale marker files alone are warnings.
- Pin GitHub-maintained Actions to the verified commits behind their reviewed major tags, remove checkout credentials, and test the oldest supported runtime with sufficient security runway (Python 3.11) plus the current stable runtime (Python 3.14).

## Deviations

- What: The post-implementation blindspot pass replaced Python 3.9/3.12 CI with Python 3.11/3.14.
  Why: Python 3.9 reached end of life on 2025-10-31 and no longer receives security updates. Python 3.11 is the oldest supported branch with more than a year of remaining security coverage, while Python 3.14 is the current stable branch as of 2026-07-11.
  Choice: Test 3.11 and 3.14 so CI covers a supported lower bound and the current stable interpreter without adding redundant matrix latency.
  Reconsider: when Python 3.11 approaches its 2027-10 end of life, advance the lower bound in a reviewed maintenance change.
  Source: https://devguide.python.org/versions/

- What: Upstream-lock validation is implemented but is optional in this PR.
  Why: The reviewed lock and consumer pins belong to Issue #6 and do not exist on `main` yet; requiring a missing lock would make this PR's CI permanently fail.
  Choice: Validate lock/marketplace/docs consistency whenever the lock exists, and enable `--require-upstream-lock` in the upstream-pinning PR.
  Reconsider: no; the final stacked PR must activate the flag before Issue #9 closes.

## Discovered Unknowns

- [UU] Claude's supported plugin listing exposes effective enablement, but there is no non-interactive supported command that resolves the exact active producer setting and its source for the current session.
- [KU] Server-, MDM-, registry-, and command-line-delivered settings cannot all be reconstructed from portable read-only filesystem inspection.
- [KU] pxpipe does not currently expose a reviewed identity/health handshake that this repository can safely verify.

## Open Questions

- Whether pxpipe will publish a stable, side-effect-free health endpoint or protocol signature suitable for identity verification.

## Follow-ups

- Issue #6 adds the upstream lock, pins all consumers, and makes lock validation mandatory in CI.
- Human operators on managed Claude installations should confirm active setting sources with `/status` when doctor reports its scope limitation.
