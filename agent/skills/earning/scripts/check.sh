#!/usr/bin/env bash
# check.sh — one-screen self-funding dashboard: runway, queue, wallet, board.
# Read-only: no claims, no spends, no token output.
set -u
AGENT="${PI_AGENT_DIR:-$HOME/.pi/agent}"
BIN="$AGENT/bin"
say() { printf '%s\n' "$*"; }
have() { [ -x "$1" ]; }

say "== self-funding rail =="

if have "$BIN/pi-frantic"; then
  if "$BIN/pi-secret" get frantic/agent-token >/dev/null 2>&1; then
    say "-- status"
    timeout 30 "$BIN/pi-frantic" status 2>&1 || say "  (status failed: token/network?)"
    say "-- queue"
    timeout 30 "$BIN/pi-frantic" queue 2>&1 || say "  (queue failed)"
    say "-- board (claimable)"
    timeout 30 "$BIN/pi-frantic" board 2>&1 | head -12 || say "  (board failed)"
  else
    say "  frantic: not configured (no pass entry frantic/agent-token)"
  fi
else
  say "  frantic: bin/pi-frantic missing"
fi

if have "$BIN/pi-own-wallet"; then
  say "-- wallet"
  timeout 30 "$BIN/pi-own-wallet" --balance 2>&1 || say "  (balance failed: RPC?)"
else
  say "  wallet: bin/pi-own-wallet missing"
fi

if have "$BIN/pi-burn"; then
  say "-- burn"
  timeout 30 "$BIN/pi-burn" 2>&1 | head -6 || say "  (burn failed: OpenRouter key/network?)"
else
  say "  burn: bin/pi-burn missing"
fi

say "-- docs"
say "  rules:    $AGENT/self-funding/PLAN.md"
say "  playbook: $AGENT/self-funding/FRANTIC.md"
say "  queue:    $AGENT/self-funding/queue.jsonl"
