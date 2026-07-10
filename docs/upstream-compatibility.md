# Upstream Compatibility And Update Policy

`config/upstreams.lock.json` is the machine-readable source of truth for the
upstream code reviewed by ASCS. The marketplace and operational commands must
match that lock. CI validates the relationship without downloading or running
upstream code.

## Reviewed set (2026-07-10)

| Component | Reviewed release | Immutable source | ASCS status |
|---|---:|---|---|
| session-health | 0.3.1 | `80b589b9120343f33decdcbc190a7d472b4ec8d3` | Stable Claude Code binding; marketplace installs this exact commit |
| compact-plus | 1.0.4 | `0f85ec8a81638683092a891e615ff3d8a04c84cc` | Stable Claude Code binding; marketplace installs this exact commit |
| pxpipe-proxy | 0.8.0 | npm integrity `sha512-zmh319/seaTOGG46TYq+kGk/RcXSuBcfHENNsIriuqqKiJWd6709DNQfqzf6J+lL+Nc1QtOg5F/TNIOe7YeTBQ==`; source `7dd54d395d119f5f822da5c1944ba5afbb02fa88` | Optional, lossy Claude Code request-path proxy |

The reviewed pxpipe package implements Anthropic Messages, OpenAI Chat
Completions, and OpenAI Responses transports. That upstream transport support
does **not** establish an ASCS Codex integration: Codex routing, authentication,
tool behavior, and byte-exact safety have not been validated end to end. The
Codex compression binding therefore remains an opt-in edge experiment and is
not part of the stable stack.

compact-plus 1.0.4 registers `UserPromptSubmit`, `PreCompact`, `PostCompact`,
and `SessionStart` hooks. Automated 10-section state generation can execute a
metered model command; ASCS keeps both LLM backends empty by default and treats
enabling them as an explicit, human-approved cost decision.

## Human-approved update workflow

Upstream drift never updates the stable channel automatically.

1. Open an issue naming the candidate version or commit and the reason to
   update. Keep the current lock active while reviewing.
2. Compare the current immutable source with the candidate. Review manifests,
   hook registrations, executable entry points, network and filesystem access,
   paid-model defaults, configuration changes, and the capabilities listed in
   the lock.
3. For npm, verify the exact version, registry tarball, integrity value, source
   repository, source commit, and Node.js/runtime requirement. Do not execute
   the package as part of the lock check.
4. Update the lock, marketplace SHA or pinned command, compatibility table,
   hook documentation, risk register, and verification date in one PR.
5. Run `python3 scripts/validate_repo.py --require-upstream-lock`, the unit
   tests, shell checks, and the plugin validator. Record all remaining
   unverified behavior in the PR.
6. A human reviews and approves the capability diff before merge. Rollback is
   a normal revert to the previous lock and marketplace SHA; do not delete the
   prior review evidence.

Candidate versions may be documented as **edge** before approval, but stable
installation examples must continue to use the locked versions.

## Primary specifications checked

- Claude Code plugin marketplace source schema, including exact GitHub `sha`:
  <https://code.claude.com/docs/en/plugin-marketplaces>
- session-health pinned source:
  <https://github.com/House-lovers7/claude-code-session-health/tree/80b589b9120343f33decdcbc190a7d472b4ec8d3>
- compact-plus pinned source:
  <https://github.com/u-ichi/compact-plus/tree/0f85ec8a81638683092a891e615ff3d8a04c84cc>
- pxpipe pinned source:
  <https://github.com/teamchong/pxpipe/tree/7dd54d395d119f5f822da5c1944ba5afbb02fa88>
- pxpipe npm package:
  <https://www.npmjs.com/package/pxpipe-proxy/v/0.8.0>

The 2026-07-10 review was static: upstream files and registry metadata were
read, but no upstream executable was run.
