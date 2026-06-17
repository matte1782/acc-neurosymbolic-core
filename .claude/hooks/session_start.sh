#!/usr/bin/env bash
mkdir -p .idos
git rev-parse HEAD > .idos/.session_start_sha 2>/dev/null \
  || printf 'no-git' > .idos/.session_start_sha
date -u +%s > .idos/.session_start_ts
echo '[framework] Read docs/decisions.md first. Plan-first.'
echo '[framework] STOP on discrepancy/ambiguity/scope-creep.'
exit 0
