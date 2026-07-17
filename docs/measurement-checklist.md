# Measurement Checklist

Use this checklist during Phase 2 experiments. Phase 1 only defines it; it does
not automate collection.

## Before The Session

- [ ] Runtime recorded: `claude-code` or `codex`.
- [ ] Stack config recorded: enabled layers and env values.
- [ ] Task goal and done definition written before work starts.
- [ ] Baseline or treated condition identified.
- [ ] Judgment rules written before reviewing outcomes.

## During The Session

- [ ] Decisions and rejected options logged.
- [ ] Failed or abandoned approaches logged with cause hypotheses.
- [ ] Checkpoint refreshed at natural boundaries.
- [ ] Bulky logs are referenced by path, not pasted into state files.
- [ ] Byte-exact values are kept as text and not trusted from summaries.

## After Compact Or Session Restart

- [ ] Handoff or checkpoint read before acting.
- [ ] Summary treated as a hypothesis and verified against source files.
- [ ] Previously rejected approaches were not re-proposed without a new reason.
- [ ] Failed attempts were not repeated unchanged.
- [ ] Prompt count until real forward progress recorded.

## Primary Metrics

- [ ] Post-compact drift count.
- [ ] Re-proposed rejected option count.
- [ ] Repeated failed approach count.
- [ ] cacheRead/output ratio where available.
- [ ] Usage or approximate cost per completed deliverable where available.
- [ ] Restart recovery prompts until forward progress.

## Secondary Metrics

- [ ] Claude Code: session-health hot/warn signals observed.
- [x] Claude Code: no-model synthetic compact-plus manual/auto marker and one-shot recovery smoke recorded (2026-07-16).
- [ ] Claude Code: real manual/auto runtime dispatch, state capture, and recovery marker behavior observed separately.
- [ ] Claude Code: pxpipe compression status observed, if enabled.
- [x] Codex: no-model JSON subprocess smoke records synthetic manual/auto trigger receipts, one-shot recovery, and sensitive-value non-persistence (2026-07-16).
- [ ] Codex: real manual/auto runtime dispatch and checkpoint trigger adherence recorded.
- [ ] Any missing state file or stale handoff recorded.

## Stop Conditions

- [ ] Any byte-exact silent confabulation incident recorded.
- [ ] Any external send, deploy, publish, or production change avoided unless
      separately approved.
- [ ] If primary metrics do not improve over baseline, do not proceed to
      generator, doctor, or measurement automation work without redesign.
