/**
 * Pi support for the custom-skills plugin. Pi loads the skills from
 * package.json's `pi.skills`; this extension supplies what Claude Code does for
 * them and pi does not:
 *
 * 1. `${CLAUDE_SKILL_DIR}`. Claude Code replaces it with the skill's directory
 *    when it loads a SKILL.md body; pi passes the body through unchanged. A
 *    `/skill:<name>` expansion gets the substitution in place. A SKILL.md read
 *    with the read tool gets a note naming the value instead, so the text an
 *    edit matches against stays the file's own. A read or bash call that still
 *    names the variable is given the directory of the skill loaded last.
 * 2. The review gate. hooks/review_gate.py refuses a `gh pr merge` that is not
 *    pinned to a reviewed head; this runs it on every bash call, with the
 *    Claude Code hook's input format and exit-code contract.
 * 3. `fresh_agent`. Skills such as `review` and `audit` start a reviewer with
 *    no access to the session's context. Pi has no built-in subagent tool; this
 *    one runs each task in a new `pi -p` process on the session's model and
 *    thinking level.
 */
import { spawn, spawnSync } from "node:child_process";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const VAR = /\$\{CLAUDE_SKILL_DIR\}|\$CLAUDE_SKILL_DIR\b/g;
const HAS_VAR = new RegExp(VAR.source);
// The block pi's /skill: expansion builds (agent-session.js _expandSkillCommand);
// text after </skill> is the user's and is not rewritten.
const SKILL_BLOCK = /^<skill name="[^"]+" location="([^"]+)">\n[\s\S]*?\n<\/skill>/;
const FRESH_AGENT_ENV = "CS_FRESH_AGENT";
const MAX_CONCURRENT = 4;
const FAILED_STOPS = new Set(["error", "aborted", "length"]);

const HERE = path.dirname(fileURLToPath(import.meta.url));
const GATE = path.join(HERE, "..", "hooks", "review_gate.py");

function resolvePath(p: string, cwd: string): string {
	if (p.startsWith("@")) p = p.slice(1); // as pi's read tool does
	if (p === "~" || p.startsWith("~/")) p = path.join(os.homedir(), p.slice(1));
	return path.resolve(cwd, p);
}

function shellQuote(s: string): string {
	return `'${s.replace(/'/g, `'\\''`)}'`;
}

type Text = { type: "text"; text: string };

function substituteBlock(text: string): string {
	return text.replace(SKILL_BLOCK, (block, location: string) =>
		block.replace(VAR, path.dirname(location)),
	);
}

function substitute(content: unknown): unknown {
	if (typeof content === "string") return substituteBlock(content);
	if (Array.isArray(content))
		return content.map((part: any) =>
			part?.type === "text" ? { ...part, text: substituteBlock(part.text) } : part,
		);
	return content;
}

function textOf(content: unknown): string {
	if (typeof content === "string") return content;
	if (Array.isArray(content))
		return content
			.filter((part: any) => part?.type === "text")
			.map((part: any) => part.text)
			.join("\n");
	return "";
}

export default function (pi: ExtensionAPI) {
	let lastSkillDir: string | undefined;

	// Python exits 2, the gate's refusal code, when the script is missing, so a
	// missing gate would block every bash call; it is skipped instead.
	const gate = fs.existsSync(GATE);
	if (!gate) console.warn(`custom-skills: ${GATE} not found; the review gate is off`);

	// Registered first so it sees the command as the model wrote it.
	pi.on("tool_call", async (event) => {
		if (!gate || event.toolName !== "bash") return undefined;
		const command = (event.input as { command?: string }).command;
		if (!command) return undefined;
		const run = spawnSync("python3", ["-I", GATE], {
			input: JSON.stringify({ tool_name: "Bash", tool_input: { command } }),
			encoding: "utf-8",
			timeout: 10_000,
		});
		// The gate lets a command through on its own internal error; a missing
		// python3 or a timeout is treated the same way.
		if (run.status === 2) {
			return { block: true, reason: run.stderr.trim() || "BLOCKED by the review gate" };
		}
		return undefined;
	});

	pi.on("tool_call", async (event) => {
		if (!lastSkillDir) return undefined;
		const input = event.input as { path?: string; command?: string };
		if (event.toolName === "read" && typeof input.path === "string") {
			input.path = input.path.replace(VAR, lastSkillDir);
		} else if (
			event.toolName === "bash" &&
			typeof input.command === "string" &&
			input.command.includes("CLAUDE_SKILL_DIR")
		) {
			input.command = `export CLAUDE_SKILL_DIR=${shellQuote(lastSkillDir)}; ${input.command}`;
		}
		return undefined;
	});

	pi.on("tool_result", async (event, ctx) => {
		if (event.toolName !== "read" || event.isError) return undefined;
		const p = (event.input as { path?: string }).path;
		if (typeof p !== "string" || path.basename(p) !== "SKILL.md") return undefined;
		const dir = path.dirname(resolvePath(p, ctx.cwd));
		lastSkillDir = dir;
		if (!event.content.some((part) => part.type === "text" && HAS_VAR.test(part.text))) {
			return undefined;
		}
		// Must not rewrite the file text: an edit's old text is copied from it.
		const note: Text = {
			type: "text",
			text:
				`In this skill, \${CLAUDE_SKILL_DIR} is ${dir}. Use that absolute path ` +
				`wherever the text below names \${CLAUDE_SKILL_DIR}.`,
		};
		return { content: [note, ...event.content] };
	});

	pi.on("context", async (event) => {
		let changed = false;
		const messages = event.messages.map((msg: any, i: number) => {
			if (msg.role !== "user") return msg;
			const match = SKILL_BLOCK.exec(textOf(msg.content));
			if (!match) return msg;
			// Only the newest message may set it; an older /skill: must not
			// override a SKILL.md read since.
			if (i === event.messages.length - 1) lastSkillDir = path.dirname(match[1]);
			if (!HAS_VAR.test(match[0])) return msg;
			changed = true;
			return { ...msg, content: substitute(msg.content) };
		});
		return changed ? { messages } : undefined;
	});

	// A fresh agent loads this extension too; it does not get the tool, so it
	// cannot start agents of its own.
	if (process.env[FRESH_AGENT_ENV]) return;

	pi.registerTool({
		name: "fresh_agent",
		label: "Fresh agent",
		description:
			"Run each task in a new pi process that has no access to this conversation, on this " +
			"session's model and thinking level; several tasks run in parallel. Returns each " +
			"agent's final message. Use when a skill says to start a fresh agent (not a fork): put " +
			"everything the agent needs in its task, because it sees nothing else.",
		parameters: Type.Object({
			tasks: Type.Array(
				Type.Object({
					task: Type.String({ description: "The complete brief for this agent" }),
					cwd: Type.Optional(Type.String({ description: "Working directory; default the session's" })),
				}),
				{ minItems: 1, description: "One entry per agent" },
			),
		}),

		async execute(_toolCallId, params, signal, _onUpdate, ctx) {
			const args = ["--mode", "json", "-p", "--no-session"];
			if (ctx.model) args.push("--model", `${ctx.model.provider}/${ctx.model.id}`);
			const thinking = pi.getThinkingLevel();
			if (thinking) args.push("--thinking", thinking);

			const results = await mapLimit(params.tasks, MAX_CONCURRENT, (t) =>
				runPi([...args, `Task: ${t.task}`], t.cwd ? resolvePath(t.cwd, ctx.cwd) : ctx.cwd, signal),
			);
			const text = results
				.map((r, i) => {
					const head = params.tasks.length > 1 ? `## Agent ${i + 1}\n\n` : "";
					// A failed agent's last text may be a partial answer; it must not
					// read as the agent's result.
					if (r.failure) return `${head}FAILED: ${r.failure}`;
					return `${head}${r.output || "(no output)"}`;
				})
				.join("\n\n");
			return {
				content: [{ type: "text", text }],
				details: undefined,
				isError: results.some((r) => r.failure),
			};
		},
	});
}

async function mapLimit<T, R>(items: T[], limit: number, f: (item: T) => Promise<R>): Promise<R[]> {
	const results: R[] = new Array(items.length);
	let next = 0;
	const worker = async () => {
		while (next < items.length) {
			const i = next++;
			results[i] = await f(items[i]);
		}
	};
	await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));
	return results;
}

type AgentResult = { output: string; failure?: string };

function runPi(args: string[], cwd: string, signal: AbortSignal | undefined): Promise<AgentResult> {
	if (signal?.aborted) return Promise.resolve({ output: "", failure: "aborted before start" });
	return new Promise((resolve) => {
		const script = process.argv[1];
		const runtime = path.basename(process.execPath).toLowerCase();
		const [command, argv] =
			script && /^(node|bun)(\.exe)?$/.test(runtime)
				? [process.execPath, [script, ...args]]
				: ["pi", args];
		const proc = spawn(command, argv, {
			cwd,
			env: { ...process.env, [FRESH_AGENT_ENV]: "1" },
			stdio: ["ignore", "pipe", "pipe"],
		});
		let buffer = "";
		let stderr = "";
		// The last assistant message decides the result. In json mode pi exits 0
		// after a provider error, so the stop reason must be read from the stream.
		let last: { text: string; stopReason?: string; errorMessage?: string } | undefined;
		const onLine = (line: string) => {
			if (!line.trim()) return;
			let event: any;
			try {
				event = JSON.parse(line);
			} catch {
				return;
			}
			if (event.type !== "message_end" || event.message?.role !== "assistant") return;
			const m = event.message;
			last = { text: textOf(m.content), stopReason: m.stopReason, errorMessage: m.errorMessage };
		};
		const finish = (code: number | null, error?: string) => {
			onLine(buffer);
			buffer = "";
			const output = last?.text ?? "";
			if (error) return resolve({ output, failure: error });
			if (last && FAILED_STOPS.has(last.stopReason ?? "")) {
				return resolve({ output, failure: `${last.stopReason}: ${last.errorMessage ?? "no message"}` });
			}
			if (code !== 0) return resolve({ output, failure: `exit ${code}: ${stderr.trim()}` });
			if (!last) return resolve({ output, failure: "no assistant message" });
			resolve({ output });
		};
		proc.stdout.on("data", (data) => {
			buffer += data.toString();
			const lines = buffer.split("\n");
			buffer = lines.pop() ?? "";
			for (const line of lines) onLine(line);
		});
		proc.stderr.on("data", (data) => {
			stderr += data.toString();
		});
		proc.on("error", (err) => finish(null, String(err)));
		proc.on("close", (code) => finish(code));
		signal?.addEventListener("abort", () => proc.kill("SIGTERM"), { once: true });
	});
}
