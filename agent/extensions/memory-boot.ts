/**
 * Memory boot extension
 *
 * Injects `mem brief` (pinned core memories, key lessons, recent entries, open PDSA cycles) into the
 * system prompt at the start of every session, so persistent memory is present without asking.
 * Cache-friendly: it writes to systemPromptOptions.sections, which Pi diffs instead of replacing.
 *
 * Usage: ~/.pi/agent/extensions/memory-boot.ts — delete to disable; `mem` stays available as a CLI.
 */

import { execFile } from "node:child_process";
import * as os from "node:os";
import * as path from "node:path";
import { promisify } from "node:util";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const run = promisify(execFile);
const MEM = path.join(os.homedir(), ".pi", "agent", "bin", "mem");

const FULL_BUDGET = 700;
/**
 * Local models get a 200-token brief: the full one is ~700 tokens, which at 7.8 tok/s of prefill
 * is 90 s of a 16k context spent on memory a 1.5B cannot use anyway (see extensions/local-slim.ts).
 */
const LOCAL_BUDGET = 200;

export default function memoryBoot(pi: ExtensionAPI) {
	const briefs = new Map<number, string>();

	async function refresh(budget: number): Promise<string> {
		if (briefs.has(budget)) return briefs.get(budget)!;
		let text = "";
		try {
			const { stdout } = await run(MEM, ["brief", "--budget", String(budget)], {
				timeout: 10_000,
				maxBuffer: 1024 * 1024,
			});
			text = (stdout ?? "").trim();
		} catch {
			text = ""; // never block a session on memory
		}
		briefs.set(budget, text);
		return text;
	}

	function isLocal(model: { provider?: string; baseUrl?: string } | undefined): boolean {
		if (!model) return false;
		if (model.provider === "local" || model.provider === "llama.cpp") return true;
		return /^https?:\/\/(127\.0\.0\.1|localhost|\[::1\])(:|\/|$)/.test(model.baseUrl ?? "");
	}

	pi.on("session_start", async (event, ctx) => {
		const brief = await refresh(FULL_BUDGET);
		if (brief) {
			ctx.ui.notify(`memory: ${brief.split("\n").filter((l) => l.startsWith("[#")).length} entries loaded`, "info");
		}
	});

	// keep the injected block fresh as memories are written during a long session
	pi.on("before_agent_start", async (event, ctx) => {
		const brief = await refresh(isLocal(ctx.model) ? LOCAL_BUDGET : FULL_BUDGET);
		if (!brief) return;
		event.systemPromptOptions.sections.session_memory = [
			"Persistent memory from earlier sessions (authoritative for machine facts, owner preferences and past decisions; supersede rather than repeat, and verify anything that looks stale):",
			brief,
			"Protocol: `mem brief` / `mem search <query>` to recall, `mem add` for new durable facts, `mem pdsa` for improvement cycles. See the memory skill.",
		].join("\n");
	});
}
