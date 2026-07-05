# When Not To Use Agent Session Control Stack

Agent Session Control Stack is for long-running AI coding sessions where
context loss, repeated failed approaches, and unsafe restart behavior are real
risks. It is not a default wrapper for every task.

Use less process when the coordination overhead is larger than the failure mode
you are trying to prevent.

## Do Not Use It Yet

### 1. Short, Low-Risk Tasks

Do not introduce ASCS for small edits, single-answer questions, or tasks that
fit comfortably in one uninterrupted session.

Examples:

- fixing a typo or a broken link
- answering a local code question
- making a small README update
- changing one obvious constant or label

For these tasks, the handoff files, checkpoints, and decision logs can cost more
attention than they save. A normal conversation plus `git diff` is usually
enough.

### 2. Work That Depends On Byte-Exact Values

Do not route byte-exact work through lossy compression. Hashes, IDs, secrets,
file paths, migration names, deploy targets, and exact error strings must remain
plain text and must be verified against source files or command output.

If byte-exact values are central to the task, either avoid the compression layer
entirely or keep those values outside the compressed path. ASCS can still be used
for checkpointing and recovery, but only if the operator keeps exact values in
verifiable text form.

### 3. Teams Without A Clear Session Owner

Do not adopt the protocol before deciding who owns the checkpoint, recovery, and
measurement discipline.

The stack assumes somebody will:

- refresh state at useful boundaries
- record rejected options and failed attempts
- treat summaries as hypotheses
- verify recovery against source files
- withdraw the stack if it does not improve the measured failure modes

Without that ownership, ASCS becomes extra files that look authoritative but may
be stale.

### 4. Before A Baseline Exists

Do not claim ASCS improves a workflow until there is a baseline to compare
against. First record how the same kind of work behaves without the stack:

- restart prompts until real forward progress
- repeated failed approach count
- re-proposed rejected option count
- post-restart or post-compact drift
- cost or token use per completed deliverable where available

The full pxpipe + session-health + compact-plus composition effect has not been
empirically validated in this repository. Treat it as a design hypothesis until
before/after data clears the withdrawal criteria.

### 5. Production Or External-Send Work Without A Separate Approval Gate

ASCS is not a substitute for release, deploy, publish, PR, issue, email, or
production-data approval. If a task can affect shared history, public artifacts,
customer data, billing, or production systems, the approval gate must be defined
outside the session-control files.

Use ASCS to preserve working state, not to authorize irreversible operations.

## Use A Smaller Slice Instead

The layers are separable. If the full stack is too much, adopt only the part
that addresses the current risk:

- Use a plain checklist when the task is short but has one critical constraint.
- Use a decision log when rejected options are likely to be forgotten.
- Use handoff notes when a restart is likely.
- Use measurement before generator or automation work.
- Use compression only when bulky context is the bottleneck and exact values are
  protected.

The default should be the smallest process that prevents the observed failure.
