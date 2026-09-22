"""Behavior checks for chat-driven plan selection in the generated sidebar."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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

    def test_new_user_task_does_not_reuse_an_old_plan_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            plan = Path(temporary) / "plans" / "old-feature"
            plan.mkdir(parents=True)
            state = plan / "plan-state.yaml"
            state.write_text('{"phases": []}')
            messages = [
                "USER: Continue plans/old-feature/plan-state.yaml",
                "ASSISTANT: Phase complete",
                "USER: Now reconcile the wallet balances",
            ]
            self.assertEqual(MODULE.select_plan(messages, [state]), state)
            self.assertEqual(MODULE.current_task_messages(messages), messages[-1:])
            self.assertIsNone(MODULE.select_plan(MODULE.current_task_messages(messages), [state]))

    def test_codex_chat_and_tool_call_can_identify_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = root / "plans" / "wallet-migration"
            plan.mkdir(parents=True)
            state = plan / "plan-state.yaml"
            state.write_text('{"phases": []}')
            transcript = root / "codex.jsonl"
            entries = [
                {"type": "response_item", "payload": {
                    "type": "message", "role": "user",
                    "content": [{"type": "input_text", "text": "Continue the implementation"}],
                }},
                {"type": "response_item", "payload": {
                    "type": "function_call", "name": "exec_command",
                    "arguments": '{"cmd":"cat plans/wallet-migration/plan-state.yaml"}',
                }},
            ]
            transcript.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
            self.assertEqual(MODULE.select_plan(MODULE.chat_messages(transcript), [state]), state)

    def test_model_resolves_chat_without_plan_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "project").mkdir()
            plan = root / "plans" / "ledger-settlement"
            plan.mkdir(parents=True)
            state = plan / "plan-state.yaml"
            state.write_text('{"phases": [{"id": "phase-01", "status": "complete"}]}')
            sessions = root / "sessions"
            sessions.mkdir()
            transcript = sessions / "chat.jsonl"
            transcript.write_text(json.dumps({
                "type": "user", "message": {"content": "Please reconcile the balances."}
            }) + "\n")
            (sessions / "claude-hook-sessions.json").write_text(json.dumps({"sessions": {
                "chat": {"sessionId": "chat", "cwd": str(root / "project"),
                         "transcriptPath": str(transcript)}
            }}))
            resolver = MODULE.ModelResolver(asynchronous=False)
            with patch.object(MODULE.ModelResolver, "classify", return_value=state) as classify:
                matched = MODULE.session_plans(sessions, [], resolver)
            self.assertEqual(matched["chat"]["completed"], 1)
            classify.assert_called_once()

    def test_model_choice_stays_stable_within_a_user_task(self):
        plan_a = Path("/plans/a/plan-state.yaml")
        plan_b = Path("/plans/b/plan-state.yaml")
        resolver = MODULE.ModelResolver(asynchronous=False)
        with patch.object(MODULE.ModelResolver, "classify", side_effect=[plan_a, plan_b]) as classify:
            first = resolver.resolve("chat", ["USER: Reconcile balances"], [plan_a, plan_b])
            same_task = resolver.resolve(
                "chat", ["USER: Reconcile balances", "ASSISTANT: Checking receipts"], [plan_a, plan_b]
            )
            next_task = resolver.resolve(
                "chat", ["USER: Reconcile balances", "USER: Update the website"], [plan_a, plan_b]
            )
        self.assertEqual((first, same_task, next_task), (plan_a, plan_a, plan_b))
        self.assertEqual(classify.call_count, 2)


if __name__ == "__main__":
    unittest.main()
