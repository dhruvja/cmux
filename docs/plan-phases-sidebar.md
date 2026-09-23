# Plan phases for the focused agent terminal

`scripts/plan-sidebar.py` generates a cmux custom sidebar from local Codex and
Claude Code conversations. It follows the focused terminal, even when several
terminals in one workspace are working on different plans. The sidebar shows
the plan's completed count, progress bar, current phase, and most recently
completed phase. A phase counts as done only when `plan-state.yaml` says
`complete`.

The generator reads cmux's local `*-hook-sessions.json` registries to find each
agent session's transcript and working directory. It looks for referenced plan
paths, phase filenames, or plan names in recent chat messages and tool calls.
It discovers plan files in `plans/` and `docs/plans/` under that directory or
its ancestors. If references do not identify one plan, it asks `codex exec` to
choose from the candidate plans. The model receives the last 12 extracted chat
items, capped at 1,200 characters each, plus plan names, up to eight phase
headings, and a short plan overview. It returns no match when unsure. Model
requests use an ephemeral, read-only Codex session. A successful inference is
kept for the current user request; unclear results can be retried after one
minute when the chat gains new context. The generated sidebar
contains session IDs and plan summaries, not chat text. The generator does not
change any plan file.

If a plan lives elsewhere, add its parent plans directory with `--plans-root`.

```bash
python3 scripts/plan-sidebar.py --plans-root /path/to/plans --watch
cmux sidebar validate plan-phases
cmux right-sidebar set custom plan-phases
```

Keep the generator running to refresh the sidebar every two seconds as chats
or plan states change. cmux hot-reloads the generated file at
`~/.config/cmux/sidebars/plan-phases.swift`. Run `cmux hooks setup` if agent
sessions do not appear in cmux. The model fallback requires an installed and
signed-in Codex CLI. An unavailable model leaves an unclear chat unmatched.

The right-sidebar command requires a cmux build with custom right-sidebar
support. Older builds can validate the generated Swift file but only offer
custom sidebars on the left. Plan files must use the JSON-compatible YAML
format written by `phased-plan-creator`; the generator needs only Python's
standard library.
