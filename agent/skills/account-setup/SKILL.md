---
name: account-setup
description: Create an account and store its credential safely — interface order (API/MCP first, browser last), pi-secret for the password, pi-mail for verification, pi-firefox for the GUI fallback. Use when the owner asks for a new account, a signup, a token, or a credential that must be stored.
---

# Account setup — identity, credential, verification, last-resort browser

One line: **generate the password in `pass`, read the verification from the shell, and only drive
the GUI one paced action at a time.**

Read first: `PASSWORDS.md` (protocol), `RUNBOOK-accounts.md` (Google/GitHub case), the
`INCIDENTS.md` entries for the GitHub bot wall and the xdotool offset.

## Interface order (owner rule)

**MCP/API → shell against the same API → browser/GUI only when no API exists or it is
credential-walled.** Signup usually has no API; the browser is the last resort, not the first.
Say so in one line when you use it.

## Checklist

1. **Identity.** Decide username, display name, email. Check what exists:
   `bin/pi-secret list`; `bin/mem search "account <service>"`.
2. **Generate, don't invent.**
   ```bash
   bin/pi-secret new <service>/<account> --user <email> --url <url> --note "<identity notes>"
   ```
   It prints the password once. Never reuse a password; never type one that was not generated.
3. **Email verification from the shell.**
   ```bash
   bin/pi-mail check
   bin/pi-mail latest --n 5
   bin/pi-mail wait --from <service> --timeout 300
   bin/pi-mail otp --from <service> --minutes 20 --len 6
   ```
   The Atom transport returns summaries, not full bodies. For a link-only email, fetch the
   conversation view with the Firefox cookies (see `bin/pi-mail` and `self-funding/FRANTIC.md`), or
   open the link with `pi-firefox goto <url>`.
4. **Browser fallback (last resort).**
   ```bash
   bin/pi-firefox list
   bin/pi-firefox goto "https://service.example/signup"
   bin/pi-firefox shot /tmp/signup.png
   bin/pi-firefox key Tab
   bin/pi-firefox move X Y
   bin/pi-firefox type "text"          # human key intervals, pauses; --typos to self-correct
   bin/pi-firefox click X Y
   bin/pi-firefox scroll 3             # smooth wheel ticks, or `scroll 3 X Y`
   ```
   Pointer and keys are shaped by `bin/pi-human` (Bezier glide, dwell, jittered hold, non-uniform
   key timing) — never call `xdotool mousemove ... click` or fixed-delay `xdotool type` yourself; a
   teleport-then-type is a bot fingerprint and the reason this step exists at all. Pacing: one action every few seconds, one attempt per stage, no reload-spamming, no parallel
   tabs of the same flow. Calibrate the click offset with one harmless click first (the window
   frame and the client area differ by ~28 px); prefer Tab+Enter over clicking. If clicks stop
   working, suspect the offset before clicking harder.
5. **Prefer SSO where offered.** Record `no-password: <provider>` in the entry; the real secret
   stays with the provider.
6. **2FA / recovery.** Add what the service asks for. Note *what* was used (phone, recovery email),
   never the code itself.
7. **Record the access path.** SSH key, token name, or "SSO only". For SSH, the public key lives in
   `~/.ssh/` and is pasted once.
8. **Verify from the terminal** before declaring success: `ssh -T git@github.com`, `pass show`,
   or a real API call. A browser "looks done" is not verification.
9. **Commit the password store.** `pi-secret` commits its own entry; check with
   `pass git -C ~/.password-store log -1`.

## Stop rules (do not loop)

- A CAPTCHA, SMS, QR or "verify your info" challenge is a **stop**, not a puzzle. Tell the owner
  exactly what is on screen and what one action is needed.
- If a service blocks the network/IP, stop. Wait 24–72 h, or use a phone on cellular data, or
  choose a different provider (Codeberg/GitLab for git). Repeated attempts extend the block.
- Never automate signup/login flows unless the owner explicitly asks you to drive it; then use the
  visible browser, one action at a time, and stop at the first challenge.

## Hard rules

- Never put a credential in `AGENTS.md`, a skill, a commit, a memory row, or a chat message.
- Never write a password to a plaintext file; `pass` is the only store.
- Never push the password store or `auth.json` to the public repo; `pi-preflight` checks this.
- Rotate on any exposure: provider first, then the store, then `pass git commit`.

## Failure modes (measured)

- **`pi-mail check` returns 401** — the Atom cookies expired. Refresh the Gmail session in Firefox,
  or enable 2-Step Verification and store an app password at `google/imap-app-password`; `pi-mail`
  switches to IMAP automatically. `bin/pi-preflight` prints `warn mail` when the transport fails.
- **`pi-firefox list` is empty** — no `DISPLAY` in this shell. `export DISPLAY=:0` and retry.
- **`pi-secret list` is empty** — the pass store is not initialized; see `PASSWORDS.md`.
- **A click does nothing** — the window-frame offset (~28 px) is the usual cause. Calibrate with a
  harmless click or use Tab+Enter; do not click harder.

## Exercise

```bash
bin/pi-secret list          # the store is readable
bin/pi-mail check           # the mail transport is live
DISPLAY=:0 bin/pi-firefox list   # the GUI fallback can see windows
```

If all three work, the skill's tools are live. If one fails, fix that transport before starting a
signup — a signup that stalls on verification is the failure this skill exists to prevent.

- **X (or any ) password "incorrect" after typing a `pass` value** — the field was not empty.
  Firefox autofills the confirm-password form, so typing the value appends to the saved one and
  the page rejects it. Click the field, `ctrl+a`, Delete, then paste; verify the dot count equals
  the password length before submitting. Measured 2026-11-20: `pass x/host` line 1 unlocked
  x.com/settings/your_twitter_data/account this way, and was byte-identical to the Firefox login
  (`logins.json` decrypted through `libnss3` `PK11SDR_Decrypt`).
