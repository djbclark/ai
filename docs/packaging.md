# Packaging `aiuse`

Distribution name / CLI: **`aiuse`**. Compatibility console script **`ai`**
calls the same entrypoint (`aiuse.ai_stub:main`).

## Status

| Channel | Status |
| --- | --- |
| Editable / venv (`pip install -e .`) | Supported (dev) |
| **pipx** from GitHub | Ready to use (see below) |
| PyPI | Name **`aiuse`** available; not published yet |
| Homebrew | Formula draft in [`packaging/homebrew/aiuse.rb`](../packaging/homebrew/aiuse.rb); not tapped yet |

External tools (`cswap`, `codexbar`, `tokscale`) stay separate PATH installs —
this package only ships the aggregator CLI.

## pipx (recommended for local “real” install)

```bash
pipx install 'git+https://github.com/djbclark/aiuse.git'
aiuse doctor
ai --version   # stub → same app
```

Upgrade:

```bash
pipx upgrade aiuse
# or reinstall from git:
pipx install --force 'git+https://github.com/djbclark/aiuse.git'
```

## PyPI (when publishing)

```bash
python -m build
twine upload dist/*
# users:
pipx install aiuse
```

Keep the PyPI project name **`aiuse`** (not `ai` — that name is taken by
Vercel’s AI SDK).

## Homebrew

Point a personal tap at [`packaging/homebrew/aiuse.rb`](../packaging/homebrew/aiuse.rb),
or copy into `homebrew-core` later. The formula installs via `pip` inside the
Cellar using the GitHub archive URL.

## Config paths after rename

- Preferred: `~/.config/aiuse/`
- Legacy still read: `~/.config/ai/` if it already has files and `aiuse` does not
- Snapshots: `~/.cache/aiuse/snapshots`

Migrate when convenient:

```bash
mkdir -p ~/.config/aiuse
cp -n ~/.config/ai/* ~/.config/aiuse/ 2>/dev/null || true
```
