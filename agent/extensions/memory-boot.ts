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

export default function memoryBoot(pi: ExtensionAPI) {
	let brief = "";

	async function refresh(): Promise<void> {
		try {
			const { stdout } = await run(MEM, ["brief", "--budget", "700"], {
				timeout: 10_000,
				maxBuffer: 1024 * 1024,
			});
			brief = (stdout ?? "").trim();
		} catch {
			brief = ""; // never block a session on memory
		}
	}

	pi.on("session_start", async (event, ctx) => {
		await refresh();
		if (brief) {
			ctx.ui.notify(`memory: ${brief.split("\n").filter((l) => l.startsWith("[#")).length} entries loaded`, "info");
		}
	});

	// keep the injected block fresh as memories are written during a long session
	pi.on("before_agent_start", async (event) => {
		if (!brief) await refresh();
		if (!brief) return;
		event.systemPromptOptions.sections.session_memory = [
			"Persistent memory from earlier sessions (authoritative for machine facts, owner preferences and past decisions; supersede rather than repeat, and verify anything that looks stale):",
			brief,
			"Protocol: `mem brief` / `mem search <query>` to recall, `mem add` for new durable facts, `mem pdsa` for improvement cycles. See the memory skill.",
		].join("\n");
	});
}
