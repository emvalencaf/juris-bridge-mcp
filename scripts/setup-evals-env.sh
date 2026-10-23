#!/usr/bin/env bash
# Write the evaluation's Gemini settings into .env (git-ignored): asks for the API key without
# echoing it and fills in the models and the limits of the maintainer's AI Studio project
# (docs/research/gemini-free-tier-rate-limits.md, 2026-10-22).
#
#   scripts/setup-evals-env.sh           ask for the key, then write the settings
#   scripts/setup-evals-env.sh --show    print the EVALS_* settings (the key is never printed)
#
# Existing lines of the same names are replaced; every other line of .env is kept.
# The limits are the lowest of the agent and judge models, which share one set of variables.
# For the calibration run (the model with 20 requests a day) override them:
#   EVALS_REQUESTS_PER_MINUTE=5 EVALS_REQUESTS_PER_DAY=20 uv run --group evals python -m evals ...
set -euo pipefail

root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
env_file="$root/.env"

settings=(
  "EVALS_AGENT_MODEL=gemini-3.5-flash-lite"   # 15 RPM, 500 RPD
  "EVALS_JUDGE_MODEL=gemini-3.1-flash-lite"   # 15 RPM, 500 RPD, a quota of its own
  "EVALS_CALIBRATION_MODEL=gemini-3.8-flash"  # 5 RPM, 20 RPD; the Pro models have 0 here
  "EVALS_REQUESTS_PER_MINUTE=15"
  "EVALS_TOKENS_PER_MINUTE=250000"
  "EVALS_REQUESTS_PER_DAY=500"
  "EVALS_MAX_REQUESTS_PER_RUN=400"
  "EVALS_ROTATE_KEYS=false"
)

if [[ "${1:-}" == "--show" ]]; then
  grep -E '^(EVALS_|GEMINI_API_KEY=)' "$env_file" 2>/dev/null | sed -E 's/^(GEMINI_API_KEY=).+/\1<set>/' || true
  exit 0
fi
[[ $# -eq 0 ]] || { sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

read -r -s -p "GEMINI_API_KEY (hidden): " key
echo
[[ -n "$key" ]] || { echo "no key given; nothing written" >&2; exit 1; }

touch "$env_file"
chmod 600 "$env_file"

# Drop the lines being set, then append them; the key goes through stdin, never the arguments.
names="GEMINI_API_KEY"
for line in "${settings[@]}"; do names+="|${line%%=*}"; done
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
grep -Ev "^(${names})=" "$env_file" > "$tmp" || true
{
  cat "$tmp"
  printf 'GEMINI_API_KEY=%s\n' "$key"
  for line in "${settings[@]}"; do printf '%s\n' "${line%%  *}"; done
} > "$env_file"

echo "Wrote the Gemini settings to $env_file (key not shown):"
"$0" --show
