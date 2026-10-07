#!/usr/bin/env python3
"""Tests for review_gate.py, offline: a fake `gh` on PATH answers `gh pr view`
for two PRs, and CS_REVIEW_DIR points at a temporary record directory.

    python3 hooks/test_review_gate.py
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
GATE = HERE / "review_gate.py"
RECORD = HERE.parent / "skills" / "review" / "references" / "record-review.sh"
SHA = {"7": "7" * 40, "8": "8" * 40}

FAKE_GH = """#!/bin/sh
# gh pr view <n> [--repo R] --json ... ; anything else fails.
[ "$1 $2" = "pr view" ] || exit 1
n=$3
case "$n" in 7|8) ;; *) echo "no such PR $n" >&2; exit 1 ;; esac
printf '{"headRefOid":"%s","url":"https://github.com/Owner/Repo/pull/%s","number":%s}\\n' \\
  "$(printf "$n%.0s" $(seq 40))" "$n" "$n"
"""


class Gate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = pathlib.Path(self.tmp.name)
        (t / "bin").mkdir()
        gh = t / "bin" / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(0o755)
        self.env = dict(os.environ, PATH=f"{t / 'bin'}:{os.environ['PATH']}",
                        CS_REVIEW_DIR=str(t / "reviews"))

    def tearDown(self):
        self.tmp.cleanup()

    def gate(self, command, tool="Bash"):
        data = {"tool_name": tool, "tool_input": {"command": command}, "cwd": self.tmp.name}
        p = subprocess.run([sys.executable, str(GATE)], input=json.dumps(data),
                           capture_output=True, text=True, env=self.env)
        return p.returncode, p.stderr

    def record(self, pr, *verdict):
        subprocess.run(["bash", str(RECORD), "owner/repo", SHA[pr], *verdict],
                       check=True, capture_output=True, env=self.env)

    def test_unrelated_commands_pass(self):
        for c in ["ls -la", 'echo "run gh pr merge later"', 'git log --grep "gh pr merge"',
                  "gh pr view 7", "gh pr merge --help"]:
            self.assertEqual(self.gate(c)[0], 0, c)
        self.assertEqual(self.gate("gh pr merge 7", tool="Read")[0], 0)

    def test_unreviewed_head_is_blocked_with_the_record_command(self):
        rc, err = self.gate("gh pr merge 7 --repo owner/repo --squash")
        self.assertEqual(rc, 2)
        self.assertIn("owner/repo#7 head 777777777777 has no recorded review", err)
        self.assertIn(str(RECORD), err)

    def test_recorded_head_passes(self):
        self.record("7", "no findings")
        self.assertEqual(self.gate("gh pr merge 7 --repo owner/repo --squash")[0], 0)

    def test_waiver_passes_and_needs_a_reason(self):
        bad = subprocess.run(["bash", str(RECORD), "owner/repo", SHA["7"], "--waive"],
                             capture_output=True, env=self.env)
        self.assertNotEqual(bad.returncode, 0)
        self.record("7", "--waive", "version bump")
        self.assertEqual(self.gate("gh pr merge 7 -R owner/repo")[0], 0)

    def test_record_of_another_head_does_not_count(self):
        self.record("8", "reviewed")
        self.assertEqual(self.gate("gh pr merge 7 --repo owner/repo")[0], 2)

    def test_every_merge_in_a_command_is_checked(self):
        self.record("7", "ok")
        rc, err = self.gate("gh pr merge 7 --repo owner/repo && gh pr merge 8 --repo owner/repo")
        self.assertEqual(rc, 2)
        self.assertIn("#8", err)

    def test_quoted_separators_and_shell_wrappers(self):
        self.record("7", "ok")
        self.assertEqual(self.gate('cd x && gh pr merge 7 --repo owner/repo '
                                   '--subject "a; b" --body "x | y"')[0], 0)
        self.assertEqual(self.gate('bash -c "gh pr merge 8 --repo owner/repo"')[0], 2)
        self.assertEqual(self.gate('eval "gh pr merge 8 --repo owner/repo"')[0], 2)
        self.assertEqual(self.gate("/usr/local/bin/gh pr merge 8 --repo owner/repo")[0], 2)

    def test_unresolvable_or_unparseable_is_refused(self):
        self.assertEqual(self.gate("gh pr merge 99 --repo owner/repo")[0], 2)
        self.assertEqual(self.gate('gh pr merge 7 --subject "unterminated')[0], 2)

    def test_internal_error_lets_the_command_through(self):
        p = subprocess.run([sys.executable, str(GATE)], input="not json",
                           capture_output=True, text=True, env=self.env)
        self.assertEqual(p.returncode, 0)


if __name__ == "__main__":
    unittest.main()
