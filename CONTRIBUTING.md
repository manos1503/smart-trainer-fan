# Contributing

## Workflow

`main` is always buildable. All work happens on short-lived branches merged through a pull request.

1. Branch off an up-to-date `main`:
   ```bash
   git switch main && git pull
   git switch -c feat/ble-power-reader
   ```
2. Commit in small, focused steps (see below).
3. Push and open a PR: `git push -u origin HEAD`, then `gh pr create --fill`.
4. CI must pass. Merge with **Squash and merge**; the PR title becomes the commit on `main`.
5. Delete the branch.

### Branch names

`<type>/<short-kebab-description>`, for example `feat/ir-learn-mode`, `fix/hr-reconnect`,
`docs/wiring-diagram`.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <imperative summary, max ~72 chars>

<optional body: what and why, not how>
```

| Type | Use for |
|---|---|
| `feat` | New behaviour |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code change with no behaviour change |
| `test` | Tests |
| `ci` | CI configuration |
| `chore` | Tooling, dependencies, housekeeping |

Scopes: `firmware`, `tools`, `hw`, `docs`, `ci`.

Examples:

```
feat(firmware): read cycling power over BLE with NimBLE
fix(tools): handle 16-bit heart-rate values
docs(hw): add IR LED driver wiring
```

## Signed commits

Every commit on `main` must be signed (enforced by the branch ruleset). SSH signing is the simplest:

```bash
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub
git config --global commit.gpgsign true
git config --global tag.gpgsign true
```

Then add the same public key on GitHub as a **Signing Key**
(Settings → SSH and GPG keys → New SSH key → Key type: Signing Key).

Squash merges done on GitHub are signed by GitHub itself.

## Code style

- Python (`tools/`): formatted and linted with `ruff` (`ruff format`, `ruff check`).
- C++ (`firmware/`): `.clang-format` at the repo root; run "Format Document" in VS Code.

## Releases

Semantic versioning. Tag milestones from `main`, e.g. `git tag -s v0.1.0 -m "BLE reading works"`,
and record them in [CHANGELOG.md](CHANGELOG.md).
