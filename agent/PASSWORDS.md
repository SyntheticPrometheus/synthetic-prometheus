# Credentials protocol

Every credential this agent creates or uses goes into `pass` (GPG, `~/.password-store`, git-versioned).
Nothing is written to a plaintext file, a repo, a shell history or a chat log.

## Store

- `pass` + a dedicated GPG key `09A9474FDB18202DB1C706A7DB757F38203F911A`
  (`SyntheticPrometheus <prometheussynthetic@gmail.com>`), no passphrase so unattended runs work.
- `~/.password-store` is `700`, every entry `600`, and the store is a git repo (encrypted history).
- Threat model, stated plainly: this protects against casual reads, accidental commits, repo leaks
  and backups of the wrong directory. It does **not** protect against root, a full disk image, or
  someone with your login session. A passphrase-protected key would, at the cost of every unattended
  run needing a human.

## Commands

```bash
pi-secret new <path> [--len 24] [--user U] [--url URL] [--note TEXT]   # generate + store, prints once
pi-secret get <path>        # password only, for a script
pi-secret show <path>       # full entry
pi-secret list
```

`pi-secret new` prints the password exactly once, for typing into a signup form; after that it only
comes back through `pass show`.

## Protocol for a new account (the repeatable part)

1. **Decide the identity first**: username, display name, email. Write it down in the entry's note.
2. **Generate, don't invent**: `pi-secret new <service>/<account> --user <email> --url <url>`.
   Never reuse a password across services; never type one that was not generated here.
3. **Sign up in the browser** (human-visible, one action at a time — see the pacing rule below).
   Paste the generated password from the terminal output.
4. **Prefer SSO where offered** (Google/Apple/GitHub). Then the entry records `no-password: <provider>`
   plus the identity, and the real secret stays with the provider.
5. **Add the second factor / recovery** the service asks for, and note in the entry what was used
   (phone, recovery email) — never the code itself.
6. **Record the access path**: SSH key, token name, or "SSO only". For SSH, the key lives in
   `~/.ssh/` and the public half is pasted once into the service.
7. **Verify from the terminal** before declaring success: `ssh -T git@…`, `pass show`, a real push.
8. **Never** put a credential in `AGENTS.md`, a skill, a commit, a memory row, or a chat message.

## Pacing rule for signup flows

One action every few seconds, one attempt per stage, no reload-spamming, no parallel tabs of the
same flow. Rapid clicking and scripted browser launches are what produced the GitHub bot block on
2026-11-14. If a page stops responding to synthetic clicks, stop and check the window offset rather
than clicking harder.

## Rotation

- If a credential is ever exposed (committed, pasted, logged): rotate it at the provider first, then
  update the store, then `pass git commit`.
- `pass git log` is the audit trail of when an entry changed.
