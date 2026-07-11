# Implementation Notes: Upstream, State, And Experiment Hardening

Date: 2026-07-10

Scope: GitHub issues #6, #7, #8, and the remaining lock requirement in #9.

## Confirmed decisions

- The stable marketplace installs session-health 0.3.1 and compact-plus 1.0.4
  by immutable GitHub SHA. pxpipe-proxy operational commands pin npm 0.8.0;
  the lock also records registry integrity and source SHA.
- Lock validation is offline. It checks marketplace SHAs, reviewed capability
  metadata, policy documentation, and every operational pxpipe command without
  executing upstream packages.
- Codex compression remains edge-only. Upstream Responses transport exists,
  but an ASCS/Codex end-to-end routing and safety result does not.
- `.agent-session/` is ignored, short-lived, untrusted recovery context. A
  read-only checker binds live state to repository, branch, commit, schema,
  writer session, update time, and expiry before content is used.
- Experiment 004 clones have every current remote push URL disabled plus
  `push.default=nothing`. Failed preparation leaves the source untouched and
  prints inspection/rollback information; it never removes partial work.
- Experiment helpers require an explicit `--target-repo`; no developer home
  directory is embedded as an operational default.
- Pair-wide events use idempotent prepare, target, and commit records. A split
  write receives abort markers and remains ineligible for pair claims until an
  identical retry completes both arms.
- The five historical Experiment 004 trees remain byte-for-byte unchanged and
  are protected by fixed Git tree IDs in tests.

## Unknowns and bounded residual risks

- [中] Claude Code's marketplace parser is documented to support a GitHub
  `sha`, but this change does not perform a real plugin install. Installation is
  a manual environment operation and may expose runtime-specific compatibility
  failures not visible to static validation.
- [高] npm integrity is recorded and exact version drift is blocked in docs;
  ASCS does not replace npm's own download/integrity enforcement and does not
  execute the package during CI lock validation.
- [中] The live state checker can detect metadata mismatch, obvious machine
  paths, private-key blocks, and common secret assignments. It cannot reliably
  classify arbitrary prose as customer/personal data; the protocol prohibition
  and human review remain necessary.
- [高] Remote push disabling protects remotes present at clone time. A user can
  deliberately reconfigure Git or add another remote later, so this is a strong
  accident guard rather than an authorization boundary.
- [高] Append-only pair transactions cannot make two files atomically durable.
  They make partial state explicit, non-claimable, and recoverable by an
  identical retry, which is the strongest local behavior available without a
  transactional event store.
- [高] Historical events contain legacy machine-specific evidence. Rewriting
  those append-only records would destroy provenance, so the hardening redacts
  all newly generated publishable notes and freezes the historical trees
  instead.

## Verification contract

Required local gates:

```bash
python3 -m unittest discover tests -v
python3 scripts/validate_repo.py --require-upstream-lock
python3 -m py_compile scripts/check_state.py scripts/exp003.py scripts/exp004.py scripts/validate_repo.py
bash -n plugins/ascs/scripts/ascs_doctor.sh
shellcheck plugins/ascs/scripts/ascs_doctor.sh
```

The prepare-arm integration tests use temporary local Git repositories only;
they do not push, call an API, or modify frozen evidence.
