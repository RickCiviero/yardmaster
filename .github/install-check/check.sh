#!/usr/bin/env bash
# Finds the Yardmaster skill that a channel installed under ROOT, runs `doctor` on it and records the outcome.
# Usage: check.sh CHANNEL ROOT. A failing doctor, a traceback or a nonzero exit fails the step. Warnings are expected:
# the formats for Copilot CLI, Claude Code and Codex are not yet verified against live installs.
set -uo pipefail
channel=$1
root=$2
found=$(find "$root" -path '*/yardmaster/scripts/yardmaster.py' 2>/dev/null | head -n 1)
if [ -z "$found" ]; then
  echo "- $channel: **not installed** (no yardmaster.py under $root)" >> "$GITHUB_STEP_SUMMARY"
  exit 1
fi
out=$(cd "$(dirname "$found")" && python yardmaster.py doctor 2>&1)
status=$?
echo "$out"
if [ "$status" -ne 0 ] || echo "$out" | grep -q '\[fail\]' || echo "$out" | grep -q 'Traceback'; then
  echo "- $channel: installed at \`$found\`, but \`doctor\` failed" >> "$GITHUB_STEP_SUMMARY"
  exit 1
fi
echo "- $channel: installed and \`doctor\` passed (warnings are expected for unverified formats)" >> "$GITHUB_STEP_SUMMARY"
