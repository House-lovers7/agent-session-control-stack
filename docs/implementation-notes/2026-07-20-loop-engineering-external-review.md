# External Review: "Loop Engineering: The Karpathy Method" (@0xCodila)

## Scope

- Input: viral article pasted into a session on 2026-07-20 (thread by
  @0xCodila; no canonical URL provided with the paste).
- Purpose: verify the article's factual claims against primary sources, and
  map its "loop engineering" framework onto existing ASCS assets so the
  article is never cited here unverified.
- Verification date: 2026-07-20 (web search + fetch of the Fortune article
  mirror). Facts below are tagged [High] only when read directly from a
  primary source or its mirror.

## Verified facts [High]

- `karpathy/autoresearch` exists: <https://github.com/karpathy/autoresearch>,
  released 2026-03-06. Three-file structure matches the article: `train.py`
  (agent-editable), `prepare.py` (frozen evaluator defining `val_bpb`),
  `program.md` (instructions and constraints). Loop shape: modify → train
  ~5 minutes → keep or revert on the metric.
- Fortune coined "The Karpathy Loop" (2026-03-17):
  <https://fortune.com/2026/03/17/andrej-karpathy-loop-autonomous-ai-agents-future/>
  (content verified via mirror
  <https://tech.yahoo.com/ai/articles/karpathy-loop-former-openai-researcher-073000966.html>).
  700 experiments over 2 days, 20 kept improvements, and an 11%
  training-time cut at GPT-2 quality (2.02h → 1.80h) — the article omits
  that last number.
- The bilevel paper exists: arXiv 2603.23420, "Bilevel Autoresearch:
  Meta-Autoresearching Itself" (Yaonan Qu, Meng Lu),
  <https://arxiv.org/abs/2603.23420>. The outer loop reads the inner loop's
  code and traces and injects new search mechanisms at runtime; 5x
  improvement on Karpathy's benchmark (-0.045 vs -0.009 val_bpb); both
  loops use the same LLM.

## Article inaccuracies — do not cite

- Lütke paragraph [High that the article is wrong]: the primary source says
  37 experiments and a 19% performance gain on an internal model. "Half the
  size" appears nowhere; the claim is likely conflated with a separate
  Liquid template-engine run reported as 120 experiments, 93 commits, 53%
  faster rendering, 61% fewer allocations.
- "Missing scalar multiplier in the attention mechanism" [Unverified]: not
  present in the Fortune article; no primary source located.
- "66,000+ stars within a month" [Unverified]: only figure found is 86,192
  stars as of 2026-06.

## Mapping: article loop components ⇔ ASCS assets

| Article component | ASCS coverage | Status |
| --- | --- | --- |
| Verifier (gate that can fail work) | `scripts/validate_repo.py`; `docs/acceptance-criteria.md`; per-item `verification_command` in `config/improvements.json` | Covered |
| State (loop memory across passes) | `.agent-session/` (current-plan, decision-log, failed-attempts, recovery-notes, checkpoint, handoff) plus the `docs/state-trust-contract.md` trust boundary | Covered; ASCS goes further (trust envelope) |
| Stop condition | `docs/measurement-checklist.md` Stop Conditions; pre-registered interruption in `experiments/README.md` | Covered |
| Maker/checker separation | fresh-context verification rule in `docs/improvement-loop.md` §2 | Covered |
| Automation / heartbeat (scheduler) | none | Non-goal: runtime responsibility (session runner, cron), not a layer of this stack |
| Connectors (issue tracker, chat) | none | Non-goal |

## Adoption candidates (human decision; not auto-promoted)

1. Bilevel framing: the improvement loop (`config/improvements.json` +
   `docs/improvement-loop.md`) is already an outer loop over this stack,
   but "the outer loop may change how the inner loop searches, not just
   its parameters" is stated nowhere. Candidate: one clarifying paragraph
   in `docs/improvement-loop.md` citing arXiv 2603.23420.
2. Loop-adoption 4-condition test (task repeats at least weekly /
   automated verification exists / token budget absorbs retry waste /
   agent has real tools): candidate pre-registration checklist item in
   `experiments/README.md` intake.

## Registry decision

Not registered in `config/improvements.json`: improvement-loop intake is
per independently verifiable problem, and this note is knowledge intake
with no confirmed defect. If a human accepts either adoption candidate, it
enters the registry as its own item at that point.
