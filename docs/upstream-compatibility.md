# Upstream Compatibility And Update Policy

`config/upstreams.lock.json` is the machine-readable source of truth for the
upstream code reviewed by ASCS. The marketplace and operational commands must
match that lock. CI validates the relationship without downloading or running
upstream code.

## Reviewed set (2026-07-10)

| Component | Reviewed release | Immutable source | ASCS status |
|---|---:|---|---|
| session-health | 0.3.1 | `80b589b9120343f33decdcbc190a7d472b4ec8d3` | Stable Claude Code binding; marketplace installs this exact commit |
| compact-plus | 1.0.4 | `0f85ec8a81638683092a891e615ff3d8a04c84cc`; `sha256-tree-v1` `e6c5fdec1134df64968fce205f9b103cb2fa13c18de43d8bf10617cd2827bde7` (26 files) | Stable Claude Code binding; marketplace installs this exact commit and Doctor attests the cached tree |
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

The Doctor packages `plugins/ascs/reviewed-upstreams.json`, a minimal runtime
snapshot of the two plugin versions and revisions above. For compact-plus it
also carries the reviewed cache-tree digest. `sha256-tree-v1` is SHA-256 over
newline-delimited compact JSON records of `[relative POSIX path, file SHA-256]`,
sorted by path. It includes every regular plugin file, excludes `.git` and
Claude Code's root-level `.in_use/<pid>` process-marker files, and rejects
links, special files, more than 2,048 reviewed files, or more than 64 MiB.
Non-PID names, deeper paths under `.in_use`, and same-named directories nested
under reviewed content remain attested.
Repository validation requires the snapshot to match
`config/upstreams.lock.json` exactly.

An enabled plugin with another installed version is reported as
`VERSION MISMATCH`. A compact-plus cache whose version matches but whose tree
does not is reported as `CONTENT MISMATCH`. Both return a non-zero status and
cannot support a stable binding claim. Missing or unsafe cache paths remain
`UNKNOWN`; Doctor never prints them. Content attestation is currently recorded
for compact-plus only. session-health remains version/revision checked.

## Synthetic Recovery Contract Smoke

After Doctor reports reviewed compact-plus version and content, run:

```bash
python3 -B scripts/smoke_compact_plus.py
```

The command executes only the reviewed PostCompact marker hook and the next
UserPromptSubmit recovery hook in isolated temporary directories. It verifies
synthetic `manual` and `auto` marker creation, one-shot consumption, recovery
context boundaries, and summary non-reinjection. See
[compact-plus synthetic recovery smoke](compact-plus-synthetic-smoke.md) for
the complete safety and claim boundary.

This raises the evidence above static inspection, but it does not prove that a
current Claude Code runtime dispatched the hooks during a real `/compact` or
auto-compaction. Real runtime dispatch remains a separately approved gate.

## Human-approved update workflow

Upstream drift never updates the stable channel automatically.

1. Open an issue naming the candidate version or commit and the reason to
   update. Keep the current lock active while reviewing.
2. Compare the current immutable source with the candidate. Review manifests,
   hook registrations, executable entry points, network and filesystem access,
   paid-model defaults, configuration changes, and the capabilities listed in
   the lock. For a content-attested plugin, recompute `sha256-tree-v1` from the
   exact pinned source and compare it with a fresh installed cache before
   changing the lock.
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

- Claude Code hook lifecycle (`PreCompact` / `PostCompact`, manual and auto
  matchers), plus the PostCompact `trigger` and `compact_summary` input fields,
  rechecked 2026-07-13:
  <https://code.claude.com/docs/en/hooks>
- Claude Code plugin marketplace source schema, including exact GitHub `sha`:
  <https://code.claude.com/docs/en/plugin-marketplaces>
- Claude Code plugin cache and version-resolution contract:
  <https://code.claude.com/docs/en/plugins-reference>
- session-health pinned source:
  <https://github.com/House-lovers7/claude-code-session-health/tree/80b589b9120343f33decdcbc190a7d472b4ec8d3>
- compact-plus pinned source:
  <https://github.com/u-ichi/compact-plus/tree/0f85ec8a81638683092a891e615ff3d8a04c84cc>
- pxpipe pinned source:
  <https://github.com/teamchong/pxpipe/tree/7dd54d395d119f5f822da5c1944ba5afbb02fa88>
- pxpipe npm package:
  <https://www.npmjs.com/package/pxpipe-proxy/v/0.8.0>

The 2026-07-10 review was static: upstream files and registry metadata were
read, but no upstream executable was run. On 2026-07-13 the Claude Code hook
contract was rechecked, the public compact-plus source was cloned into an
isolated temporary directory at the pinned commit, and all 26 non-git files
matched the installed 1.0.4 cache byte-for-byte. No compact-plus hook or model
was executed in that source/cache comparison. Later the two reviewed recovery
hooks passed the isolated synthetic `manual` and `auto` contract smoke; no
PreCompact hook, Claude session, model, or API was used. The local `installed_plugins.json`
`gitCommitSha` still named the prior v1.0.3 commit after the update; because
that field is undocumented and stale in this observed case, ASCS does not use
it as trust evidence. Exact installed content plus synthetic hook execution
still does not prove real manual/auto runtime dispatch, so that gate remains
separate.
