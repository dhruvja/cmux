#!/usr/bin/env python3
"""Render a phased-plan-creator plan as a cmux right-sidebar panel."""

import argparse
import json
import sys
import time
from pathlib import Path


def phase_title(plan_dir: Path, phase: dict) -> str:
    phase_file = plan_dir / phase.get("file", "")
    if phase_file.is_file():
        for line in phase_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    return phase.get("id", "Unnamed phase")


def load_plan(state_path: Path) -> dict:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    phases = state.get("phases", [])
    if not isinstance(phases, list):
        raise ValueError("plan-state.yaml must contain a phases array")

    return {
        "name": state_path.parent.name.replace("-", " ").title(),
        "completed": sum(phase.get("status") == "complete" for phase in phases),
        "total": len(phases),
        "phases": [
            {
                "id": phase["id"],
                "title": phase_title(state_path.parent, phase),
                "status": phase.get("status", "pending").replace("_", " "),
                "done": phase.get("status") == "complete",
            }
            for phase in phases
        ],
    }


def render(mapping_path: Path) -> str:
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError("mapping must be a non-empty object of workspace directories to plan-state paths")
    plans = {}
    for workspace_dir, plan_path in mapping.items():
        if not isinstance(workspace_dir, str) or not isinstance(plan_path, str):
            raise ValueError("workspace directories and plan-state paths must be strings")
        state_path = Path(plan_path).expanduser()
        if not state_path.is_absolute():
            state_path = mapping_path.parent / state_path
        directory = str(Path(workspace_dir).expanduser()).rstrip("/") or "/"
        plans[directory] = load_plan(state_path.resolve())

    def quoted(value: str) -> str:
        return json.dumps(value, ensure_ascii=False)

    lines = [
        f"// Generated from {mapping_path}. Edit the plans or mapping, not this file.",
        "VStack(alignment: .leading, spacing: 8) {",
        '  Text("Phases").font(.headline)',
        "  Divider()",
        "  ForEach(workspaces.filter { $0.selected }.prefix(1)) { selected in",
    ]
    for index, (workspace_dir, plan) in enumerate(plans.items()):
        lead = "if" if index == 0 else "else if"
        count_text = f"{plan['completed']} / {plan['total']} done"
        lines.extend([
            f"    {lead} selected.directory == {quoted(workspace_dir)} {{",
            f"      Text({quoted(plan['name'])}).font(.subheadline).foregroundColor(.secondary)",
            f"      Text({quoted(count_text)}).font(.caption)",
            f"      ProgressView(value: {plan['completed']}, total: {max(plan['total'], 1)})",
        ])
        for phase in plan["phases"][:30]:
            icon = "checkmark.circle.fill" if phase["done"] else "circle"
            color = "#34C759" if phase["done"] else "#8E8E93"
            lines.extend([
                "      HStack(spacing: 8) {",
                f"        Image(systemName: {quoted(icon)}).foregroundColor({quoted(color)})",
                "        VStack(alignment: .leading, spacing: 2) {",
                f"          Text({quoted(phase['title'])}).font(.caption).lineLimit(2)",
                f"          Text({quoted(phase['status'])}).font(.caption2).foregroundColor(.secondary)",
                "        }",
                "        Spacer()",
                "      }",
            ])
        if len(plan["phases"]) > 30:
            lines.append(f'      Text("{len(plan["phases"]) - 30} more phases").font(.caption2)')
        lines.append("    }")
    lines.extend([
        "    else {",
        '      Text("No plan mapped to this workspace").foregroundColor(.secondary)',
        "    }",
        "  }",
        "  Spacer()",
        "}",
        ".padding(12)",
    ])
    return "\n".join(lines) + "\n"


def write_if_changed(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapping", type=Path, help="JSON mapping of workspace directories to plan-state paths")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".config/cmux/sidebars/plan-phases.swift",
    )
    parser.add_argument("--watch", action="store_true", help="refresh when the plan changes")
    args = parser.parse_args()
    mapping_path = args.mapping.expanduser().resolve()
    while True:
        try:
            changed = write_if_changed(args.output.expanduser(), render(mapping_path))
            if changed:
                print(f"Updated {args.output}", flush=True)
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"plan-sidebar: {error}", file=sys.stderr, flush=True)
            if not args.watch:
                return 1
        if not args.watch:
            return 0
        time.sleep(2)


if __name__ == "__main__":
    raise SystemExit(main())
