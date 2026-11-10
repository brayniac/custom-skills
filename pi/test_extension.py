#!/usr/bin/env python3
"""End-to-end test of pi/extension.ts against a scripted model. Needs pi on
PATH (or PI=<path>); the CI guests do not have it, so run it locally when
pi/, package.json, hooks/review_gate.py or skills/review/ changes:

    python3 pi/test_extension.py

A local HTTP server plays an OpenAI-compatible model. Its reply depends on how
many tool results the request already carries, so one `pi -p` run walks the
script below: read a SKILL.md, read and run through `${CLAUDE_SKILL_DIR}`,
attempt an unpinned merge, start three fresh agents, one of which fails. A
second run sends `/skill:review`. Each request is recorded, and the assertions
read what the model was shown. pi runs with its own config directory, which
installs this checkout as its one package, and a temporary review record
directory, so nothing installed on this machine is loaded or consulted.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = pathlib.Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "review"
PI = os.environ.get("PI") or shutil.which("pi")
# User text after a skill block, which must reach the model unchanged.
ARGS = "fix the lines that name ${CLAUDE_SKILL_DIR}"

SCRIPT = [
    ("read", {"path": str(SKILL / "SKILL.md")}),
    ("read", {"path": "${CLAUDE_SKILL_DIR}/references/record-review.sh", "limit": 3}),
    ("bash", {"command": "echo DIR=$CLAUDE_SKILL_DIR; ls ${CLAUDE_SKILL_DIR}/references"}),
    ("bash", {"command": "gh pr merge 7 --repo owner/repo --squash"}),
    ("fresh_agent", {"tasks": [{"task": "say hi"}, {"task": "say bye"}, {"task": "fail now"}]}),
]


def text_of(content):
    if isinstance(content, str):
        return content
    return "".join(p.get("text", "") for p in content or [] if isinstance(p, dict))


def first_user(body):
    users = [text_of(m.get("content")) for m in body["messages"] if m["role"] == "user"]
    return users[0] if users else ""


class Model(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Model.requests.append(body)
        user = first_user(body)
        k = sum(1 for m in body["messages"] if m["role"] == "tool")
        if user.startswith("Task: fail"):
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"error": {"message": "scripted failure"}}')
            return
        if user.startswith("Task:"):
            delta, finish = {"content": "agent finished: " + user[5:].strip()}, "stop"
        elif user.startswith("<skill"):
            delta, finish = {"content": "skill received"}, "stop"
        elif k < len(SCRIPT):
            name, args = SCRIPT[k]
            call = {"index": 0, "id": f"call_{k}", "type": "function",
                    "function": {"name": name, "arguments": json.dumps(args)}}
            delta, finish = {"tool_calls": [call]}, "tool_calls"
        else:
            delta, finish = {"content": "done"}, "stop"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        chunks = [
            {"choices": [{"index": 0, "delta": {"role": "assistant", **delta}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
             "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}},
        ]
        for chunk in chunks:
            chunk.update({"id": "x", "object": "chat.completion.chunk", "model": "mock"})
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")


class Extension(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PI:
            raise unittest.SkipTest("pi not found; set PI=<path> or install pi")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Model)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = pathlib.Path(cls.tmp.name)
        agent = tmp / "agent"
        agent.mkdir()
        port = cls.server.server_address[1]
        (agent / "models.json").write_text(json.dumps({"providers": {"mock": {
            "api": "openai-completions", "baseUrl": f"http://127.0.0.1:{port}/v1",
            "apiKey": "x", "models": [{"id": "mock"}]}}}))
        # Installed through settings, as `pi install` does, so the processes
        # fresh_agent starts load the package too.
        (agent / "settings.json").write_text(json.dumps({"packages": [str(REPO)]}))
        cls.env = dict(os.environ, PI_CODING_AGENT_DIR=str(agent),
                       CS_REVIEW_DIR=str(tmp / "reviews"))
        cls.env.pop("CS_FRESH_AGENT", None)
        cls.cwd = tmp / "cwd"
        cls.cwd.mkdir()

        cls.tools = cls.run_pi("go")
        cls.skill = cls.run_pi("/skill:review " + ARGS)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    @classmethod
    def run_pi(cls, prompt):
        Model.requests = []
        subprocess.run(
            [PI, "--no-session", "--model", "mock/mock", "-p", prompt],
            cwd=cls.cwd, env=cls.env, check=True, capture_output=True, timeout=120,
            stdin=subprocess.DEVNULL,  # pi reads a piped stdin into the prompt
        )
        return list(Model.requests)

    def tool_results(self):
        main = [r for r in self.tools if not first_user(r).startswith("Task:")]
        last = max(main, key=lambda r: len(r["messages"]))
        return [text_of(m["content"]) for m in last["messages"] if m["role"] == "tool"]

    def test_reading_a_skill_names_its_directory(self):
        result = self.tool_results()[0]
        self.assertIn(f"${{CLAUDE_SKILL_DIR}} is {SKILL}.", result)
        # The file text itself is unchanged, so an edit still matches it.
        self.assertIn("${CLAUDE_SKILL_DIR}/references/record-review.sh", result)

    def test_a_read_through_the_variable_reaches_the_file(self):
        self.assertIn("Record that a head commit", self.tool_results()[1])

    def test_a_bash_call_through_the_variable_gets_the_directory(self):
        result = self.tool_results()[2]
        self.assertIn(f"DIR={SKILL}\n", result)
        self.assertIn("record-review.sh", result)

    def test_an_unpinned_merge_is_blocked(self):
        self.assertIn("BLOCKED by the review gate", self.tool_results()[3])

    def test_fresh_agents_run_and_cannot_start_agents(self):
        result = self.tool_results()[4]
        self.assertIn("agent finished: say hi", result)
        self.assertIn("agent finished: say bye", result)
        fresh = [r for r in self.tools if first_user(r).startswith("Task:")]
        self.assertGreaterEqual(len(fresh), 3)
        for r in fresh:
            names = [t["function"]["name"] for t in r.get("tools", [])]
            self.assertIn("bash", names)
            self.assertNotIn("fresh_agent", names)

    def test_a_failed_fresh_agent_is_reported_as_failed(self):
        result = self.tool_results()[4]
        self.assertIn("## Agent 3\n\nFAILED", result)
        self.assertNotIn("## Agent 1\n\nFAILED", result)

    def test_a_skill_command_is_substituted_in_place(self):
        user = first_user(self.skill[0])
        self.assertTrue(user.startswith('<skill name="review"'))
        block, args = user.rsplit("</skill>", 1)
        self.assertNotIn("CLAUDE_SKILL_DIR", block)
        self.assertIn(f"{SKILL}/references/record-review.sh", block)
        self.assertEqual(args.strip(), ARGS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
