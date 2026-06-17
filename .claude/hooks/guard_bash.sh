#!/usr/bin/env bash
input=$(cat 2>/dev/null || printf '')
for pat in 'rm -rf /' 'rm -rf ~' 'git push --force' \
  'DROP TABLE' 'mkfs' 'dd if='; do
  if printf '%s' "$input" | grep -qF "$pat"; then
    echo "[guard] blocked destructive pattern: $pat" >&2
    exit 2
  fi
done
exit 0
