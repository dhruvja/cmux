# Plan phases in the right sidebar

`scripts/plan-sidebar.py` turns `phased-plan-creator` `plan-state.yaml` files into a
cmux custom sidebar. The panel follows the selected cmux workspace. It shows
the completed count, progress bar, and each phase's recorded status. A phase is
counted as done only when its state says `complete`.

The right-sidebar command requires a cmux build with custom right-sidebar
support. Older builds can validate this generated Swift file but only offer
custom sidebars on the left.

Create a JSON mapping from each workspace directory to its plan state:

```json
{
  "/absolute/path/to/project": "/absolute/path/to/plans/feature/plan-state.yaml"
}
```

The workspace directory must match the directory cmux reports for that
workspace. Use `cmux current-workspace --json` to check it. Add one entry for
each workspace that should show a plan. A workspace without a mapping shows
"No plan mapped to this workspace".

Generate the sidebar once:

```bash
python3 scripts/plan-sidebar.py ~/.config/cmux/plan-sidebar-map.json
cmux sidebar validate plan-phases
cmux right-sidebar set custom plan-phases
```

Run the generator with `--watch` in a terminal to refresh it every two seconds
as the plan state or phase titles change. cmux hot-reloads the generated
`~/.config/cmux/sidebars/plan-phases.swift` file on save.

```bash
python3 scripts/plan-sidebar.py ~/.config/cmux/plan-sidebar-map.json --watch
```

The generator accepts the JSON-compatible YAML format written by the plan
skill. It uses only Python's standard library. It reads plan files and writes
the generated sidebar file; it does not change plan state.
