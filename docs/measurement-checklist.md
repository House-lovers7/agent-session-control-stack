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
- [ ] Claude Code: compact-plus state capture and recovery marker behavior observed.
- [ ] Claude Code: pxpipe compression status observed, if enabled.
- [ ] Codex: checkpoint trigger adherence recorded.
- [ ] Any missing state file or stale handoff recorded.

## Stop Conditions

- [ ] Any byte-exact silent confabulation incident recorded.
- [ ] Any external send, deploy, publish, or production change avoided unless
      separately approved.
- [ ] If primary metrics do not improve over baseline, do not proceed to
      generator, doctor, or measurement automation work without redesign.
