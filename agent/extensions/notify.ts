/**
 * Desktop notification when pi finishes a reply.
 *
 * Fires once per settled run (agent_settled), only in the interactive TUI, so headless
 * subagent runs (`pi -p`, `--mode json`) never notify. The bubble shows the last
 * assistant line(s) plus how long the run took, and a later run replaces it instead of
 * stacking.
 *
 * A chime plays with the bubble (paplay, so it follows the system sink volume).
 *
 * Usage: ~/.pi/agent/extensions/notify.ts — delete to disable, or set PI_NOTIFY=0 in the
 * environment. Also honoured: PI_NOTIFY_MIN_SECONDS (default 0), PI_NOTIFY_SOUND (default
 * /usr/share/sounds/freedesktop/stereo/complete.oga; "0" mutes it).
 */

import { execFile } from "node:child_process";
import * as path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const NOTIFY_SEND = "/usr/bin/notify-send";
const PA_PLAY = "/usr/bin/paplay";
const MIN_SECONDS = Number(process.env.PI_NOTIFY_MIN_SECONDS ?? "0") || 0;
const SOUND = process.env.PI_NOTIFY_SOUND ?? "/usr/share/sounds/freedesktop/stereo/complete.oga";

function clean(text: string, max: number): string {
	const flat = text
		.replace(/```[\s\S]*?```/g, " [code] ")
		.replace(/[#*_`>]/g, "")
		.replace(/\s+/g, " ")
		.trim();
	return flat.length > max ? `${flat.slice(0, max - 1)}…` : flat;
}

function humanDuration(ms: number): string {
	const s = Math.round(ms / 1000);
	if (s < 90) return `${s}s`;
	return `${Math.floor(s / 60)}m ${s % 60}s`;
}

function assistantText(content: unknown): string {
	if (typeof content === "string") return content;
	if (!Array.isArray(content)) return "";
	return content
		.filter((part) => {
			const p = part as { type?: string; text?: unknown };
			return p?.type === "text" && typeof p.text === "string";
		})
		.map((part) => (part as { text: string }).text)
		.join("\n");
}

export default function notify(pi: ExtensionAPI) {
	if (process.env.PI_NOTIFY === "0") return;
	if (!process.env.DISPLAY && !process.env.WAYLAND_DISPLAY) return;

	// Chime after the bubble is accepted; system sink volume/mute still apply.
	function play(): void {
		if (SOUND === "0" || SOUND === "") return;
		execFile(PA_PLAY, [SOUND], { timeout: 5_000 }, () => {});
	}

	let startedAt = 0;
	let lastReply = "";
	let lastId: number | undefined;
	let queued: Promise<void> = Promise.resolve();

	function send(title: string, body: string): void {
		// serialized so notify-send -p can hand back the id used to replace the last bubble
		queued = queued
			.then(
				() =>
					new Promise<void>((resolve) => {
						const args = ["-a", "pi", "-i", "dialog-information", "-u", "normal", "-t", "6000", "-p"];
						if (lastId !== undefined) args.push("-r", String(lastId));
						args.push(title, body);
						const done = (err: Error | null, stdout: string) => {
							if (!err) {
								const id = Number.parseInt((stdout ?? "").trim(), 10);
								if (Number.isFinite(id)) lastId = id;
							}
							resolve(); // a missing daemon must never break a session
							if (!err) play();
						};
						execFile(NOTIFY_SEND, args, { timeout: 5_000 }, (err, stdout) => done(err, stdout ?? ""));
					}),
			)
			.catch(() => {});
	}

	pi.on("agent_start", async () => {
		startedAt = Date.now();
		lastReply = "";
	});

	pi.on("message_end", async (event) => {
		const message = event.message as { role?: string; content?: unknown };
		if (message.role !== "assistant") return;
		const text = assistantText(message.content);
		if (text.trim()) lastReply = text;
	});

	pi.on("agent_settled", async (event, ctx) => {
		if (ctx.mode !== "tui") return; // subagents and headless runs stay silent
		if (event.aborted) {
			send("pi — interrupted", path.basename(ctx.cwd) || ctx.cwd);
			return;
		}
		const elapsed = startedAt ? Date.now() - startedAt : 0;
		if (elapsed / 1000 < MIN_SECONDS) return;
		const project = path.basename(ctx.cwd) || ctx.cwd;
		const title = elapsed >= 2000 ? `pi — reply ready (${humanDuration(elapsed)})` : "pi — reply ready";
		const body = lastReply ? `${project}: ${clean(lastReply, 200)}` : `${project}: task finished`;
		send(title, body);
	});
}
