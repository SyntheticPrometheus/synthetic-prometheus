/**
 * Session topic in the terminal title.
 *
 * Pi only puts `π - <cwd>` in the title, and xfce4-terminal then shows `Terminal - π - host`
 * for every window — useless when three chats are open. This extension labels each window with
 * what its session is about:
 *
 *   π - window labels for terminals - host
 *   ↯ π - window labels for terminals - host     (while the agent is working)
 *
 * Topic precedence: `/topic <text>` (explicit, this run only) > session name (`/name`, `--name`) >
 * first user message of the session (persisted, so a resumed session keeps its label) > cwd.
 * The first message is condensed: code blocks, links and markdown markers dropped, cut at a
 * sentence or word boundary. Control characters are stripped, so a prompt cannot inject a title
 * escape sequence.
 *
 * The spinner is off if `PI_TITLE_SPINNER=0`; it writes one escape per 150 ms only while a run is
 * in flight, and every title update also happens on prompt / settle / rename, which is what
 * self-heals Pi's own `π - <cwd>` re-assertions after a model change or a resume.
 */

import * as path from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

const APP = "π";
const MAX_TOPIC = 46;
const SPINNER = process.env.PI_TITLE_SPINNER !== "0";
const FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

/** Drop anything that could act on the terminal, then flatten to one line. */
function sanitize(text: string): string {
	return text
		.replace(/[\u0000-\u001f\u007f-\u009f\u2028\u2029]/g, " ")
		.replace(/\s+/g, " ")
		.trim();
}

function condense(raw: string, max = MAX_TOPIC): string {
	const flat = sanitize(
		raw
			.replace(/```[\s\S]*?```/g, " ")
			.replace(/`[^`]*`/g, " ")
			.replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
			.replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
			.replace(/https?:\/\/\S+/g, " ")
			.replace(/^[#>*+-]+\s*/gm, ""),
	);
	if (flat.length <= max) return flat;
	const head = flat.slice(0, max + 1);
	const sentence = head.search(/[.!?](\s|$)/);
	if (sentence >= 12) return head.slice(0, sentence);
	const space = head.lastIndexOf(" ");
	return `${(space >= 12 ? head.slice(0, space) : flat.slice(0, max)).trimEnd()}…`;
}

function userText(content: unknown): string {
	if (typeof content === "string") return content;
	if (!Array.isArray(content)) return "";
	return content
		.filter((part) => {
			const p = part as { type?: string; text?: unknown };
			return p?.type === "text" && typeof p.text === "string";
		})
		.map((part) => (part as { text: string }).text)
		.join(" ");
}

function firstUserPrompt(ctx: ExtensionContext): string | undefined {
	for (const entry of ctx.sessionManager.getEntries()) {
		const e = entry as { type?: string; message?: { role?: string; content?: unknown } };
		if (e.type !== "message" || e.message?.role !== "user") continue;
		const topic = condense(userText(e.message.content));
		if (topic) return topic;
	}
	return undefined;
}

export default function sessionTitle(pi: ExtensionAPI) {
	let manual: string | undefined;
	let fromSession: string | undefined;
	let timer: ReturnType<typeof setInterval> | null = null;
	let frame = 0;

	const interactive = process.stdout.isTTY === true;

	function baseTitle(ctx: ExtensionContext): string {
		const cwd = sanitize(path.basename(ctx.sessionManager.getCwd() || process.cwd()));
		const named = sanitize(pi.getSessionName() ?? "");
		const topic = manual ?? (named || fromSession || "");
		const parts = [APP];
		if (topic) parts.push(topic);
		if (cwd && topic.toLowerCase() !== cwd.toLowerCase()) parts.push(cwd);
		return parts.join(" - ");
	}

	function paint(ctx: ExtensionContext, mark?: string): void {
		if (!interactive) return;
		const title = baseTitle(ctx);
		ctx.ui.setTitle(mark ? `${mark} ${title}` : title);
	}

	function refresh(ctx: ExtensionContext): void {
		const mark = timer ? FRAMES[frame % FRAMES.length] : undefined;
		paint(ctx, mark);
	}

	function stopTimer(ctx: ExtensionContext): void {
		if (timer) {
			clearInterval(timer);
			timer = null;
			frame = 0;
		}
		paint(ctx);
	}

	pi.on("session_start", async (_event, ctx) => {
		fromSession ??= firstUserPrompt(ctx);
		paint(ctx);
	});

	pi.on("session_info_changed", async (_event, ctx) => {
		paint(ctx);
	});

	pi.on("input", async (event, ctx) => {
		const text = (event.text ?? "").trim();
		if (!fromSession && text && !text.startsWith("/") && !text.startsWith("!")) {
			fromSession = condense(text);
		}
		paint(ctx);
	});

	pi.on("agent_start", async (_event, ctx) => {
		if (!interactive || !SPINNER) return;
		stopTimer(ctx);
		timer = setInterval(() => {
			frame++;
			paint(ctx, FRAMES[frame % FRAMES.length]);
		}, 150);
		timer.unref?.();
		paint(ctx, FRAMES[0]);
	});

	pi.on("agent_settled", async (_event, ctx) => {
		stopTimer(ctx);
	});

	pi.on("session_shutdown", async (_event, ctx) => {
		stopTimer(ctx);
	});

	pi.registerCommand("topic", {
		description: "Set the window title topic (empty to fall back to the session's first message)",
		handler: async (args, ctx) => {
			const wanted = sanitize(args ?? "");
			manual = wanted ? condense(wanted) : undefined;
			refresh(ctx);
			ctx.ui.notify(`Title: ${baseTitle(ctx)}`, "info");
		},
	});
}
