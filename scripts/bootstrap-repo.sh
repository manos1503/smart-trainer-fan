#!/usr/bin/env bash
# One-time setup: create the GitHub repo, make the first signed commit, protect main.
# Requirements: git, GitHub CLI (`brew install gh`, then `gh auth login`),
# and commit signing configured (see CONTRIBUTING.md → Signed commits).
set -euo pipefail

REPO="smart-trainer-fan"
OWNER="$(gh api user --jq .login)"

cd "$(dirname "$0")/.."

if [[ "$(git config --get commit.gpgsign || true)" != "true" ]]; then
  echo "Commit signing is not enabled. Follow CONTRIBUTING.md → Signed commits first." >&2
  exit 1
fi

git init -b main
git add .
git commit -S -m "chore: initial project scaffold"
git log --show-signature -1

gh repo create "$OWNER/$REPO" --public --source=. --remote=origin --push \
  --description "ESP32 smart fan for indoor cycling: fan speed follows trainer power and heart rate over BLE"

# Protect main: PRs only, CI must pass, signed commits, no force-push or deletion.
gh api -X POST "repos/$OWNER/$REPO/rulesets" --input - <<'JSON'
{
  "name": "protect-main",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "required_signatures" },
    { "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false,
        "allowed_merge_methods": ["squash"]
      } },
    { "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          { "context": "Build firmware" },
          { "context": "Lint Python tools" }
        ]
      } }
  ]
}
JSON

# Squash-only merges, auto-delete merged branches.
gh repo edit "$OWNER/$REPO" --enable-squash-merge --enable-merge-commit=false \
  --enable-rebase-merge=false --delete-branch-on-merge

echo "Done: https://github.com/$OWNER/$REPO"
