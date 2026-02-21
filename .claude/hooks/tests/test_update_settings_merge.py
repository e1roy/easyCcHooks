#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

import easyCcHooks as hooks


def _reset_registry():
    for hook_list in hooks.HookRegistry._hooks.values():
        hook_list.clear()


class UpdateSettingsMergeTests(unittest.TestCase):
    def setUp(self):
        _reset_registry()
        hooks.HookRegistry.scan_and_register(quiet=True)

    def test_preserves_manual_hooks_and_removes_stale_managed_hooks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / "settings.json"
            manual_pre_tool = {
                "matcher": "Bash",
                "hooks": [{
                    "type": "command",
                    "command": "python3 /tmp/manual_pre.py"
                }]
            }
            manual_notification = {
                "matcher": "*",
                "hooks": [{
                    "type": "command",
                    "command": "python3 /tmp/manual_notification.py"
                }]
            }
            stale_managed = {
                "hooks": [{
                    "type": "command",
                    "command": 'python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/easyCcHooks.py execute OldHook'
                }]
            }
            settings_path.write_text(
                json.dumps({
                    "hooks": {
                        "PreToolUse": [manual_pre_tool, stale_managed],
                        "SessionEnd": [stale_managed],
                        "Notification": [manual_notification]
                    },
                    "env": {"keep": True}
                }, ensure_ascii=False),
                encoding="utf-8"
            )

            hooks.ConfigManager.update_settings(settings_path, backup=False)
            updated = json.loads(settings_path.read_text(encoding="utf-8"))

            self.assertEqual(updated["env"], {"keep": True})
            self.assertIn("Notification", updated["hooks"])
            self.assertEqual(updated["hooks"]["Notification"], [manual_notification])
            self.assertIn(manual_pre_tool, updated["hooks"]["PreToolUse"])
            self.assertNotIn("SessionEnd", updated["hooks"])
            self.assertNotIn(stale_managed, updated["hooks"]["PreToolUse"])


if __name__ == "__main__":
    unittest.main()
