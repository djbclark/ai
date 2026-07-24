# Packaging `aiuse`

Distribution name / CLI: **`aiuse`**. Compatibility console script **`ai`**
calls the same entrypoint (`aiuse.ai_stub:main`).

## Status

| Channel                              | Status                                                                             |
| ------------------------------------ | ---------------------------------------------------------------------------------- |
| Editable / venv (`pip install -e .`) | Supported (dev)                                                                    |
| **pipx** from GitHub                 | Ready                                                                              |
| **pipx** from PyPI                   | Live: `pipx install aiuse`                                                         |
| Trusted Publishing (OIDC)            | Configured — Release / `workflow_dispatch` via `publish.yml`                       |
| **Homebrew** personal tap            | Live: `brew tap djbclark/aiuse && brew trust djbclark/aiuse && brew install aiuse` |
| homebrew-core                        | Not submitted                                                                      |

External tools (`cswap`, `codexbar`, `tokscale`) stay separate PATH installs —
this package only ships the aggregator CLI.

## Version note

Git tag **`v2.0.0`** is historical (pre-rename `src/ai/`). First renamed
release was **`2.1.0`**; current is **`2.1.1`** (OIDC publish verify).

## pipx

From PyPI (preferred once published):

```bash
pipx install aiuse
aiuse doctor
ai --version   # stub → same app
```

From GitHub tip (works today):

```bash
pipx install 'git+https://github.com/djbclark/aiuse.git'
```

Upgrade:

```bash
pipx upgrade aiuse
# or force reinstall from git:
pipx install --force 'git+https://github.com/djbclark/aiuse.git'
```

## PyPI

Build and check locally:

```bash
uv run --with build --with twine python -m build
uv run --with twine twine check dist/*
```

**Automated publish:** GitHub Release `published` runs
[`.github/workflows/publish.yml`](../.github/workflows/publish.yml) with
Trusted Publishing (OIDC). Environment **`pypi`** already exists on the repo.

### Trusted Publishing (OIDC) — configured

PyPI trusted publisher is set for owner `djbclark`, repo `aiuse`, workflow
`publish.yml`, environment `pypi`. Publishing a GitHub Release (or running
`gh workflow run publish.yml`) uploads with OIDC — no token in Actions.

Keep the PyPI project name **`aiuse`** (not `ai` — taken by Vercel’s AI SDK).

### Manual upload via secretspec (token)

Declarations: [`secretspec.toml`](../secretspec.toml). Value in gitignored `.env`
(dotenv provider).

```bash
secretspec set PYPI_TOKEN          # one-time; prompts if omitted
secretspec check -n --explain
uv run --with build python -m build
secretspec run --reason "publish aiuse to PyPI" -- \
  bash -lc 'uv publish --token "$PYPI_TOKEN" dist/*'
```

OIDC is preferred for CI; the token path is for optional local `uv publish`.

## Homebrew

Canonical formula copy:
[`packaging/homebrew/aiuse.rb`](../packaging/homebrew/aiuse.rb).

Tap repo: https://github.com/djbclark/homebrew-aiuse

```bash
brew tap djbclark/aiuse
brew trust djbclark/aiuse   # Homebrew requires trusting third-party taps
brew install aiuse
```

Verified: Cellar installs `aiuse` / `ai` (refresh formula after each tag).

After cutting a new release, refresh formula `url` / `version` / `sha256` here
and sync `Formula/aiuse.rb` in the tap:

```bash
curl -sL "https://github.com/djbclark/aiuse/archive/refs/tags/vX.Y.Z.tar.gz" \
  | shasum -a 256
```

## Release checklist (maintainers)

1. Bump `version` in `pyproject.toml` and `__version__` in `src/aiuse/__init__.py`.
2. `.venv/bin/python -m pytest -q` — green.
3. `git tag -a vX.Y.Z -m "…"` && push tag (SSH if HTTPS lacks `workflow` scope).
4. `python -m build` && `gh release create vX.Y.Z dist/* …`
5. Publish workflow uploads to PyPI (after trusted publisher is configured).
6. Refresh Homebrew formula + tap `sha256`.

## Config paths

- Config: `~/.config/aiuse/` (`services.yaml`, `config.toml`)
- Snapshots: `~/.cache/aiuse/snapshots`

The old `~/.config/ai/` path is no longer read. If you still have files there:

```bash
mkdir -p ~/.config/aiuse
cp -n ~/.config/ai/* ~/.config/aiuse/
```
