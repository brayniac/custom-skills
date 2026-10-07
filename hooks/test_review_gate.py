#!/usr/bin/env python3
"""Tests for review_gate.py and record-review.sh. Offline: the gate reads only
the command and the record directory, which CS_REVIEW_DIR points at a
temporary directory.

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
A, B = "a" * 40, "b" * 40
PINNED = f"gh pr merge 7 --repo owner/repo --match-head-commit {A} --squash"


class Gate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = dict(os.environ, CS_REVIEW_DIR=str(pathlib.Path(self.tmp.name) / "reviews"))

    def tearDown(self):
        self.tmp.cleanup()

    def gate(self, command, tool="Bash"):
        data = {"tool_name": tool, "tool_input": {"command": command}, "cwd": self.tmp.name}
        p = subprocess.run([sys.executable, str(GATE)], input=json.dumps(data),
                           capture_output=True, text=True, env=self.env)
        return p.returncode, p.stderr

    def blocked(self, command):
        return self.gate(command)[0] == 2

    def record(self, *args):
        return subprocess.run(["bash", str(RECORD), *args], capture_output=True,
                              text=True, env=self.env)

    def test_commands_that_do_not_merge_pass(self):
        for c in ["ls -la", 'echo "run gh pr merge later"', 'git log --grep "gh pr merge"',
                  "gh pr view 7", "gh pr merge --help", "gh pr merge 7 --disable-auto",
                  "git commit -F - <<'EOF'\nrefuse `gh pr merge` of a head; the review's record\nEOF",
                  "gh pr create --body-file - <<EOF\nthen gh pr merge 3 once green\nEOF"]:
            self.assertFalse(self.blocked(c), c)
        self.assertEqual(self.gate("gh pr merge 7", tool="Read")[0], 0)

    def test_an_unpinned_merge_is_refused_with_the_form_to_use(self):
        rc, err = self.gate("gh pr merge 7 --repo owner/repo --squash")
        self.assertEqual(rc, 2)
        self.assertIn("--match-head-commit", err)
        self.assertTrue(self.blocked(f"gh pr merge --match-head-commit {A} --squash"))
        self.assertTrue(self.blocked(f"gh pr merge 7 --repo owner/repo --match-head-commit abc123"))

    def test_a_pinned_merge_needs_a_record_of_that_sha(self):
        rc, err = self.gate(PINNED)
        self.assertEqual(rc, 2)
        self.assertIn(f"owner/repo {A[:12]} has no recorded review", err)
        self.assertIn(str(RECORD), err)
        self.assertEqual(self.record("owner/repo", B, "merge", "ok").returncode, 0)
        self.assertTrue(self.blocked(PINNED))
        self.assertEqual(self.record("Owner/Repo", A, "merge", "no blocking findings").returncode, 0)
        self.assertFalse(self.blocked(PINNED))
        self.assertFalse(self.blocked(f"gh pr merge https://github.com/owner/repo/pull/7 "
                                      f"--match-head-commit {A}"))

    def test_every_way_of_writing_the_merge_is_seen(self):
        for c in ["gh -R owner/repo pr merge 7", "gh --repo owner/repo pr merge 7",
                  "gh pr -R owner/repo merge 7", 'gh pr "merge" 7 --repo owner/repo',
                  "gh pr m\\erge 7 --repo owner/repo", "echo `gh pr merge 7 --repo owner/repo`",
                  "x=$(gh pr merge 7 --repo owner/repo)", 'bash -lc "gh pr merge 7 --repo owner/repo"',
                  'sh -ec "gh pr merge 7 --repo owner/repo"', 'eval "gh pr merge 7 --repo owner/repo"',
                  "/usr/local/bin/gh pr merge 7 --repo owner/repo",
                  "cd ../other && gh pr merge 7 --squash",
                  f"{PINNED} && gh pr merge 8 --repo owner/repo"]:
            self.assertTrue(self.blocked(c), c)

    def test_api_merges_and_auto_are_refused(self):
        self.record("owner/repo", A, "merge", "ok")
        for c in ["gh api -X PUT repos/owner/repo/pulls/7/merge",
                  "gh api graphql -f query='mutation { mergePullRequest(input: {}) { clientMutationId } }'",
                  f"{PINNED} --auto"]:
            self.assertTrue(self.blocked(c), c)

    def test_quoted_separators_do_not_split_a_merge(self):
        self.record("owner/repo", A, "merge", "ok")
        self.assertFalse(self.blocked(f'cd x && {PINNED} --subject "a; b" --body "x | y"'))

    def test_a_merge_that_does_not_tokenise_is_refused(self):
        self.assertTrue(self.blocked(f'{PINNED} --subject "unterminated'))

    def test_record_review_takes_a_sha_and_a_verdict_of_merge_or_waive(self):
        self.assertNotEqual(self.record("owner/repo", "12", "merge", "ok").returncode, 0)
        self.assertNotEqual(self.record("owner/repo", A, "fix-first", "x").returncode, 0)
        self.assertNotEqual(self.record("owner/repo", A, "--waive").returncode, 0)
        self.assertEqual(self.record("owner/repo", A, "--waive", "version bump").returncode, 0)
        self.assertFalse(self.blocked(PINNED))

    def test_an_internal_error_lets_the_command_through(self):
        p = subprocess.run([sys.executable, str(GATE)], input="not json",
                           capture_output=True, text=True, env=self.env)
        self.assertEqual(p.returncode, 0)


if __name__ == "__main__":
    unittest.main()
