#!/usr/bin/env bash
mkdir -p .idos
LOG=.idos/session_log.jsonl
payload=$(cat 2>/dev/null || printf '{}')
sha0=$(cat .idos/.session_start_sha 2>/dev/null || printf 'unknown')
sha1=$(git rev-parse HEAD 2>/dev/null || printf 'unknown')
ts0=$(cat .idos/.session_start_ts 2>/dev/null || printf '0')
ts1=$(date -u +%s)
dur=$((ts1 - ts0))
if [ "$sha0" = 'unknown' ] || [ "$sha0" = 'no-git' ]; then
  stat=$(git diff --shortstat 2>/dev/null || printf '')
else
  stat=$(git diff --shortstat "$sha0" 2>/dev/null || printf '')
fi
files=$(printf '%s' "$stat" | grep -oE '[0-9]+ file' | head -1 | grep -oE '[0-9]+' || printf '0')
ins=$(printf '%s' "$stat" | grep -oE '[0-9]+ insertion' | head -1 | grep -oE '[0-9]+' || printf '0')
dels=$(printf '%s' "$stat" | grep -oE '[0-9]+ deletion' | head -1 | grep -oE '[0-9]+' || printf '0')
if [ -z "$files" ]; then files=0; fi
if [ -z "$ins" ]; then ins=0; fi
if [ -z "$dels" ]; then dels=0; fi
adr=$(git diff "$sha0" -- docs/decisions.md 2>/dev/null | grep -c '^+## ADR' || true)
if [ -z "$adr" ]; then adr=0; fi
tpath=$(printf '%s' "$payload" | sed -n 's/.*"transcript_path"[ ]*:[ ]*"\([^"]*\)".*/\1/p')
tests=0
stops=0
if [ -n "$tpath" ] && [ -f "$tpath" ]; then
  if grep -qiE 'pytest|npm test|cargo test|go test' "$tpath"; then tests=1; fi
  stops=$(grep -ciE '\[STOP\]|STOP:' "$tpath" || true)
  if [ -z "$stops" ]; then stops=0; fi
fi
# Single printf with all fields so the emitted line is always valid JSON
# (collapsed per FILE 6 note + Phase B B4 acceptance: the line must parse).
printf '{"v":1,"ts":"%s","dur_s":%s,"sha0":"%s","sha1":"%s","files":%s,"ins":%s,"dels":%s,"adr":%s,"tests":%s,"stops":%s}\n' \
  "$ts1" "$dur" "$sha0" "$sha1" "$files" "$ins" "$dels" "$adr" "$tests" "$stops" >> "$LOG"
exit 0
