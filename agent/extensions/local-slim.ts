/**
 * Local-model prompt slimming
 *
 * Measured 2026-11-16: the full harness prompt is 12,670 tokens (31,108 chars of system prompt +
 * 19,559 chars of tool declarations) and llama.cpp on this box prefills at 7.8 tok/s at depth, so
 * one cold turn costs ~1800 s. Against the router's -c 16384 with maxTokens 2048 that leaves
 * 16384-2048-12924 = 1.4k tokens of free context: the first tool result overflowed, compaction
 * fired, and every compaction is another 12.9k prefill. That is the "16k fills up immediately
 * then times out" failure, and the context size was never the cause — the prompt was.
 *
 * Where the 12,670 went (captured the real request body, tokenized it on the router; numbers in
 * ~/.pi/agent/local/prompt-layers.json):
 *   AGENTS.md 2.7k, skills list 2.2k, MCP tool declarations 4.6k (laya+web+repomap),
 *   memory brief 0.7k, pi docs pointer 0.3k, base prompt + 4 core tools 0.9k.
 *
 * A 1.5B/3B cannot use 25 skill descriptions, nine MCP tools or 2.7k tokens of host policy. So
 * when the active model is local this handler keeps what a small model can actually use —
 * read/bash/edit/write, a short operating note, and (from memory-boot) a 200-token memory brief —
 * and drops the rest. It sets `customPrompt`, because Pi generates the base preamble, <tools>,
 * <rules> and the pi-docs pointer only when no custom prompt is set; a compact customPrompt is the
 * only way to drop the docs pointer, which a 1.5B will never follow.
 *
 * Measured on the same request: 12,588 -> 1,409 tokens of prompt+tools (1,663 tokens for the whole
 * first request on the 3B, 1,524 on the 1.5B), 4 tools.
 *
 * Not removable from here: the built-in MCP extension writes its own <mcp_servers> section after
 * every before_agent_start handler (measured), so ~170 tokens naming tool groups describe tools
 * this profile does not declare. Harmless; noted so it is not mistaken for a leak.
 *
 * Cloud models are untouched. PI_LOCAL_SLIM=0 disables it; PI_LOCAL_SLIM_VERBOSE=1 notifies the
 * rendered prompt size on each run.
 */

import { buildSystemPrompt } from "@earendil-works/pi-coding-agent";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

/** Tools a small local model can drive reliably. Everything else is dead weight in the prompt. */
const KEEP_TOOLS = new Set(["read", "bash", "edit", "write"]);

const LOCAL_PROMPT = `You are a coding assistant running inside pi on this host's CPU-only local model (2 cores, no
GPU). You have read, bash, edit and write. Reading costs you ~0.13 s per token, so the whole
operating contract is short:

- At most 5 lines of prose per reply. No tables, no restating the question, no code unless asked.
- One tool call per turn. Read a file before editing it; name the path in the reply.
- Never paste more than 10 lines of a file. Summarise instead.
- If a task needs more than 3 steps, write the plan as 3 bullets and do only the first step;
  the human will say continue.
- If you cannot do something with read/bash/edit/write, say so in one line and stop.
- Use a tool only to inspect or change something the user named. When the user asks for text, answer
  with text and call no tool at all.
- If a tool returns an error, do not repeat the same call: change the arguments or answer without
  tools. Never invent file contents to pass to edit; only edit text you have read.
- A repeated identical tool call is a loop and will be refused.`;

/**
 * A local model can burn 20 minutes calling tools that cannot work. Measured: Llama-3.2-3B asked to
 * "reply with exactly: ready" called `read` on a directory (EISDIR), then `read "mem pdsa"`
 * (ENOENT), i.e. it invented arguments rather than answering — and it does that with a *new* bad
 * argument each time, so blocking identical repeats alone does not stop it. So the guards are
 * structural, and scoped to local models with counters reset per run:
 *   * a repeat of the same call is refused (the result cannot change);
 *   * 3 consecutive failed calls end the run — legitimate work does not fail 3 times in a row, an
 *     inventing model always does;
 *   * a hard call budget, so one session cannot spin for an hour.
 */
const MAX_IDENTICAL = 1; // the first call is allowed, an identical repeat is not
const MAX_CONSECUTIVE_ERRORS = 3;
const MAX_CALLS = 12;


function isLocal(model: { provider?: string; baseUrl?: string } | undefined): boolean {
	if (!model) return false;
	if (model.provider === "local" || model.provider === "llama.cpp") return true;
	// any loopback endpoint is this box, whatever the provider is called
	return /^https?:\/\/(127\.0\.0\.1|localhost|\[::1\])(:|\/|$)/.test(model.baseUrl ?? "");
}

export default function localSlim(pi: ExtensionAPI) {
	if (process.env.PI_LOCAL_SLIM === "0") return;

	let seen = new Map<string, number>();
	let calls = 0;
	let errors = 0;

	pi.on("agent_start", async () => {
		seen = new Map();
		calls = 0;
		errors = 0;
	});

	pi.on("tool_result", async (event, ctx) => {
		if (!isLocal(ctx.model)) return;
		errors = event.isError ? errors + 1 : 0;
	});

	pi.on("tool_call", async (event, ctx) => {
		if (!isLocal(ctx.model)) return;
		calls += 1;
		if (errors >= MAX_CONSECUTIVE_ERRORS) {
			return {
				block: true,
				terminate: true,
				reason:
					`Stopped: the last ${MAX_CONSECUTIVE_ERRORS} tool calls failed, so more calls will ` +
					`fail too. Answer the user with what you have, or say what you need.`,
			};
		}
		if (calls > MAX_CALLS) {
			return {
				block: true,
				terminate: true,
				reason:
					`Stopped: this run already made ${MAX_CALLS} tool calls. Answer the user with what ` +
					`you have.`,
			};
		}
		let key: string;
		try {
			key = `${event.toolName} ${JSON.stringify(event.input)}`;
		} catch {
			return;
		}
		const n = (seen.get(key) ?? 0) + 1;
		seen.set(key, n);
		if (n > MAX_IDENTICAL) {
			return {
				block: true,
				reason:
					`You already called ${event.toolName} with exactly these arguments, so the result ` +
					`will not change. Do not repeat it: answer the user with what you have.`,
			};
		}
	});

	pi.on("before_agent_start", async (event, ctx) => {
		if (!isLocal(ctx.model)) return;
		const o = event.systemPromptOptions;
		const before = event.systemPrompt.length;

		// 1. Tools: the MCP declarations alone are 4.6k tokens, and codemode/subagent are
		//    unusable at 5-12 tok/s anyway.
		o.selectedTools = o.selectedTools.filter((t) => KEEP_TOOLS.has(t));
		o.hiddenTools = o.hiddenTools.filter((t) => KEEP_TOOLS.has(t));

		// 2. Compact preamble: replaces Pi's base prompt, <tools>, <rules> and the docs pointer.
		o.customPrompt = LOCAL_PROMPT;

		// 3. Sections a small model cannot act on.
		delete o.sections.docs;
		delete o.sections.skills; // 25 skill descriptions, ~2.2k tokens
		delete o.sections.session_memory; // memory-boot re-adds a 200-token brief for local models

		// 4. AGENTS.md (2.7k tokens of delegation, publishing, PDSA policy) -> a project note that
		//    tells the model what this context is for, and nothing it cannot use.
		o.contextFiles = [];
		o.skills = [];

		if (process.env.PI_LOCAL_SLIM_VERBOSE === "1") {
			const after = buildSystemPrompt(o).length;
			ctx.ui.notify(
				`local-slim: ${ctx.model?.provider}/${ctx.model?.id} prompt ${before} -> ${after} chars`,
				"info",
			);
		}
	});
}
