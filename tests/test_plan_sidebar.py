"""Behavior checks for chat-driven plan selection in the generated sidebar."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/plan-sidebar.py"
SPEC = importlib.util.spec_from_file_location("plan_sidebar", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PlanSidebarTests(unittest.TestCase):
    def test_focused_terminals_can_use_different_plans_in_one_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            plans = root / "plans"
            sessions = root / "sessions"
            sessions.mkdir()
            for slug, status in (("alpha-feature", "complete"), ("beta-feature", "pending")):
                plan = plans / slug
                plan.mkdir(parents=True)
                (plan / "plan-state.yaml").write_text(json.dumps({
                    "phases": [{"id": "phase-01", "file": "01-phase.md", "status": status}]
                }))
                (plan / "01-phase.md").write_text(f"# {slug} phase\n")

            records = {}
            for session_id, slug in (("chat-alpha", "alpha-feature"), ("chat-beta", "beta-feature")):
                transcript = sessions / f"{session_id}.jsonl"
                transcript.write_text(json.dumps({
                    "type": "user", "message": {"content": f"Continue plans/{slug}/plan-state.yaml"}
                }) + "\n")
                records[session_id] = {
                    "sessionId": session_id,
                    "transcriptPath": str(transcript),
                    "cwd": str(project),
                }
            (sessions / "claude-hook-sessions.json").write_text(json.dumps({"sessions": records}))

            matched = MODULE.session_plans(sessions, [])
            self.assertEqual(matched["chat-alpha"]["completed"], 1)
            self.assertEqual(matched["chat-beta"]["completed"], 0)

    def test_ambiguous_chat_does_not_choose_a_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidates = []
            for slug in ("alpha-feature", "beta-feature"):
                plan = root / "plans" / slug
                plan.mkdir(parents=True)
                state = plan / "plan-state.yaml"
                state.write_text('{"phases": []}')
                candidates.append(state)
            message = "Compare plans/alpha-feature/ and plans/beta-feature/"
            self.assertIsNone(MODULE.select_plan([message], candidates))


if __name__ == "__main__":
    unittest.main()
