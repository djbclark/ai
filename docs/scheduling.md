# Scheduling `aiuse` (LaunchAgent)

Regular runs accumulate snapshots under `~/.cache/aiuse/snapshots` when
`analysis.persist_snapshots` is true (see [`history-learning.md`](history-learning.md)).
This is the foundation for history insights without changing pace scoring until
you opt into `learn_from_history`.

**Primary:** macOS **LaunchAgent** every **6 hours**.  
**Footnote:** cron one-liner at the bottom.

Exit codes (for log / monitor tooling): see [`json-contract.md`](json-contract.md).

| Code  | Meaning for a scheduled run                                               |
| ----- | ------------------------------------------------------------------------- |
| **0** | OK, no burn/conserve alerts                                               |
| **1** | Hard failure (treat as error)                                             |
| **2** | OK collection; at least one burn/conserve alert (not a scheduler failure) |

## Quick install

Requires `aiuse` on `PATH` (`pipx install aiuse` or Homebrew tap).

```bash
cd /path/to/aiuse   # or: git clone https://github.com/djbclark/aiuse.git
chmod +x packaging/launchd/install.sh
./packaging/launchd/install.sh
```

The script:

1. Resolves the absolute path to `aiuse`
2. Ensures `analysis.persist_snapshots: true` in `~/.config/aiuse/services.yaml`
   (creates a minimal file if missing; does not flip `learn_from_history`)
3. Writes `~/Library/LaunchAgents/com.djbclark.aiuse.plist`
4. `launchctl bootstrap` + kickstart once
5. Logs to `~/Library/Logs/aiuse/`

## Manual install

1. In `~/.config/aiuse/services.yaml`:

   ```yaml
   analysis:
     persist_snapshots: true
     learn_from_history: false # enable later; see history-learning.md
   ```

2. Copy [`packaging/launchd/com.djbclark.aiuse.plist`](../packaging/launchd/com.djbclark.aiuse.plist),
   replace `AIUSE_BIN` with `$(command -v aiuse)` (absolute path) and `LOG_DIR`
   with `$HOME/Library/Logs/aiuse`, then:

   ```bash
   mkdir -p ~/Library/Logs/aiuse ~/Library/LaunchAgents
   # after editing the plist:
   cp com.djbclark.aiuse.plist ~/Library/LaunchAgents/
   launchctl bootstrap gui/"$(id -u)" ~/Library/LaunchAgents/com.djbclark.aiuse.plist
   launchctl kickstart -k gui/"$(id -u)"/com.djbclark.aiuse
   ```

## Verify

```bash
launchctl print gui/"$(id -u)"/com.djbclark.aiuse | head
ls -lt ~/.cache/aiuse/snapshots | head
aiuse --full -q --no-tui | head -20   # look for "History: N snapshots …"
tail -n 20 ~/Library/Logs/aiuse/aiuse.stderr.log
```

## Uninstall

```bash
launchctl bootout gui/"$(id -u)"/com.djbclark.aiuse
rm -f ~/Library/LaunchAgents/com.djbclark.aiuse.plist
```

## Cron footnote

```cron
0 */6 * * *  /path/to/aiuse -q --json >>"$HOME/Library/Logs/aiuse/cron.stdout.log" 2>>"$HOME/Library/Logs/aiuse/cron.stderr.log"
```

Prefer LaunchAgent on macOS (sleep/wake and `RunAtLoad` behave better than cron).
