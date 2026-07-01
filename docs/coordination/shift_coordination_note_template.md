---
title: Shift Coordination Note Template
slug: shift-coordination-note-template
type: reference
status: live
created: 2026-06-24
updated: 2026-06-24
owner: Wei Alexander Xin
scope: project
project: RAV
---

# Shift Coordination Note Template

*Last updated: YYYY-MM-DD*
*Target length: 250-600 words*
*Purpose: short coordination memo for concurrent work or handoff. Do not restate the full repo. Current-state context belongs in `live_repo_summary.md`; removed/stale detail belongs in `repo_summary_history.md`.*
*Handoff Brain vs shift note: the per-session **Handoff Brain** (Goal / Key files + decisions / Commands + outcomes / Next steps / Do-not-re-read) is single-sourced in the session state file `.agent-sessions/state-{uuid}.md`, the canonical state file named in `CLAUDE.md` / `AGENTS.md` § Session Registry (the brain's structure is specified in `CLAUDE.md` § Session Registry). This shift note carries **project-facing coordination facts** (cross-session deltas, current shared state, open loops affecting other agents); it is not a second copy of the brain. Keep the brain in the state file and reference it here rather than pasting it.*
*Local-only note: in most repos, `shift_coordination_note__*.md` files should remain local/untracked.*

## Position in the coordination hierarchy

This doc is one of the project coordination surfaces:

1. `CLAUDE.md` / `AGENTS.md` - durable repo-wide conventions, loaded at session start.
2. `.claude/rules/*.md` or equivalent - path-scoped conventions.
3. `live_repo_summary.md` - current state of the repo.
4. `shift_coordination_note__*.md` - short per-agent-session deltas.
5. `repo_summary_history.md` - rolling archive of removed historical detail.

## Filename convention

Each agent maintains its own persistent shift note. Concurrent sessions do not
share a single file.

```text
shift_coordination_note__<provider>_<sessionid8>_<lane>_<slug>.md
```

- `<provider>` - `claude`, `codex`, or another agent family name.
- `<sessionid8>` - stable 8-character session prefix/suffix used by the project.
- `<lane>` - repo lane code, domain code, or `aux` for non-governed sessions.
- `<slug>` - kebab-case description of the session focus.

The session ID segment is the identity anchor and should not change. Lane and
short description may change; if they do, rename the file while keeping the
same session ID segment.

Add this field to the agent/session state file when available:

```text
coordination_note: docs/coordination/shift_coordination_note__<provider>_<sessionid8>_<lane>_<slug>.md
```

## Startup recovery rule

1. Run `/coord-update pull` or read the live summary plus sibling shift notes.
2. Look for your own note via `coordination_note:` in your state file.
3. If that field is missing or stale, recover by globbing on your session id.
4. If no file exists, create one using the naming convention above.

## Cadence

- Read all sibling `shift_coordination_note__*.md` files at the start of each
  turn at minimum, and more often during long turns as needed.
- Write your own note with `/coord-update agent` before yielding control back to
  the user, and more often during long turns when the material delta changes.

## Compaction / pruning rule

A shift note is a working buffer, not a session transcript. The 250-600 word
target is a maintenance budget; once the note grows past it, compact rather
than appending forever.

Compact your own note before yielding when any of these are true:

- it is over roughly 600 words or 20 bullets
- it is longer than the live-summary section it is supposed to support
- a material commit, PR, issue closeout, proof run, or doc update has made the
  detailed work log recoverable elsewhere
- older bullets describe completed work rather than active coordination risk

Compaction procedure:

1. Keep only active deltas, current truths, open loops, next actions, and
   "ignore / not a blocker" guidance.
2. Promote settled current-state facts to `live_repo_summary.md` if they are not
   already there.
3. Add one condensed `repo_summary_history.md` entry only for displaced context
   that is not already recoverable from commits, PR / issue comments,
   `CHANGELOG.md`, validation logs, meeting notes, or run artifacts.
4. Drop command-by-command, review-loop, and local exploration minutiae once the
   result is captured in durable artifacts.
5. Rewrite the shift note in place. Do not append a summary below the old long
   note.

Preservation test:

- keep it in the shift note if the next agent needs it to act now
- keep it in the live summary if it is current repo truth
- keep it in history if it explains a state transition not otherwise recorded
- rely on commits, PRs, issues, logs, and run artifacts for full detail whenever
  possible

## Live-summary window policy

`live_repo_summary.md` should name an explicit emphasis window, but that window
is configurable by repo cadence and is not an automatic eviction timer. Older
facts can stay live when they remain blockers, proof anchors, or necessary
context. Move material to `repo_summary_history.md` only when enough newer active
work has displaced it from the live memo.

## Retirement pattern

Content flows through the coordination surfaces in one direction:

```text
shift_coordination_note__*.md -> live_repo_summary.md -> repo_summary_history.md
```

- Leaving a shift note: move settled facts into `live_repo_summary.md`.
- Leaving the live summary: move displaced or stale detail into
  `repo_summary_history.md`.
- Retiring the shift note itself: delete it only after its unique content has
  graduated into the live summary or history doc.

## Recommended structure

A note is an identity header plus **one dated update section that you rewrite in
place each turn** — do not stack update blocks (see the Compaction / pruning rule
above). The body headings below are what `/coord-update agent` emits and what
sibling agents read.

### Header (top of file)

```text
# Shift Coordination Note - <provider> / <sessionid8> / <lane> / <slug>

*Session-UUIDs: <full-session-uuid>*
*Created: <ISO 8601 timestamp>*
*Last updated: <ISO 8601 timestamp>*
*Mode: <one line: this session's focus>*
```

### Body — one `## Update` section

```text
## Update — YYYY-MM-DD HH:MM TZ

### Completed this session
- <what you finished this turn>

### What's now true
- **[V]** <verified fact>
- **[I]** <inference>
- **[?]** <unresolved>

### Open loops
- <loop>: current blocker -> next action

### Sibling deltas observed
- <delta seen in a sibling shift note or shared state; "none" if nothing>

### Q&A bank proposals
- **[open-question | decision]** <one-line proposal for the Q&A bank>
```

`### Sibling deltas observed` and `### Q&A bank proposals` are coord-update
features — include them whenever there is anything to report; a tiny / aux
session may omit them when genuinely empty. Fold "stale-live flags for the
orchestrator to reconcile" into Open loops or What's now true.

The old fixed fields map forward: **coordination mode** → the `Mode:` header line;
the session's **biggest-change / biggest-open** summary and **ordered next-steps** →
the per-session Handoff Brain in `.agent-sessions/state-{uuid}.md` (reference it,
don't duplicate it here); **"not a blocker"** items → fold into Open loops.

## Style rules

- Prefer 8-20 bullets or 5-10 short paragraphs.
- Name exact issues, PRs, run IDs, and SHAs where useful.
- Use absolute dates, not relative dates.
- Keep it much shorter than `live_repo_summary.md`.
- Avoid deep history. If you need older context, point to `repo_summary_history.md`.
- Do not duplicate the full proof ledger unless one proof result changed this shift.
