# Packaging `aiuse`

Distribution name / CLI: **`aiuse`**. Compatibility console script **`ai`**
calls the same entrypoint (`aiuse.ai_stub:main`).

## Status

| Channel | Status |
| --- | --- |
| Editable / venv (`pip install -e .`) | Supported (dev) |
| **pipx** from GitHub | Ready |
| **pipx** from PyPI | Ready after first `v2.1.0` publish (trusted publishing) |
| **Homebrew** personal tap | Formula at [`packaging/homebrew/aiuse.rb`](../packaging/homebrew/aiuse.rb); tap `djbclark/aiuse` |
| homebrew-core | Not submitted |

External tools (`cswap`, `codexbar`, `tokscale`) stay separate PATH installs —
this package only ships the aggregator CLI.

## Version note

Git tag **`v2.0.0`** is historical (pre-rename `src/ai/`). First release of the
renamed package is **`2.1.0`** / tag **`v2.1.0`**.

## pipx

From PyPI (preferred once published):

```bash
pipx install aiuse
aiuse doctor
ai --version   # stub → same app
```

From GitHub tip:

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

**Automated publish:** pushing a GitHub Release for tag `vX.Y.Z` runs
[`.github/workflows/publish.yml`](../.github/workflows/publish.yml) with
Trusted Publishing (OIDC). One-time PyPI setup:

1. Create project **`aiuse`** on PyPI (or let the first trusted upload create it).
2. PyPI → Account settings → Publishing → Add a new pending publisher:
   - Owner: `djbclark`
   - Repository: `aiuse`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`
3. In GitHub → Settings → Environments, create environment **`pypi`**
   (optional protection rules).

Manual upload (API token) if needed:

```bash
twine upload dist/*
```

Keep the PyPI project name **`aiuse`** (not `ai` — taken by Vercel’s AI SDK).

## Homebrew

Canonical formula copy lives in this repo:
[`packaging/homebrew/aiuse.rb`](../packaging/homebrew/aiuse.rb).

Install from the personal tap:

```bash
brew tap djbclark/aiuse
brew install aiuse
```

The formula uses the tagged GitHub archive (`v2.1.0`) plus `sha256`. After
cutting a new release:

```bash
# compute archive checksum
curl -sL "https://github.com/djbclark/aiuse/archive/refs/tags/vX.Y.Z.tar.gz" \
  | shasum -a 256
# update url / version / sha256 in packaging/homebrew/aiuse.rb
# sync the same file into the homebrew-aiuse tap Formula/aiuse.rb
```

Tap repo naming: GitHub repo `djbclark/homebrew-aiuse` → `brew tap djbclark/aiuse`.

## Release checklist (maintainers)

1. Bump `version` in `pyproject.toml` and `__version__` in `src/aiuse/__init__.py`.
2. `.venv/bin/python -m pytest -q` (or `uv run pytest`) — green.
3. `git tag -a vX.Y.Z -m "…"` && `git push origin vX.Y.Z`.
4. `python -m build` && attach `dist/*` to a GitHub Release (or let Actions build).
5. Publish the GitHub Release → publish workflow uploads to PyPI.
6. Refresh Homebrew formula `url` / `sha256` / `version`; push tap.

## Config paths

- Config: `~/.config/aiuse/` (`services.yaml`, `config.toml`)
- Snapshots: `~/.cache/aiuse/snapshots`

The old `~/.config/ai/` path is no longer read. If you still have files there:

```bash
mkdir -p ~/.config/aiuse
cp -n ~/.config/ai/* ~/.config/aiuse/
```
