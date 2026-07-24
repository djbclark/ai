# Snapshot history and learning

`aiuse` can persist each collect under `~/.cache/aiuse/snapshots/` and later
blend that history into pace scoring / chronic-waste alerts.

## Config flags

In `~/.config/aiuse/services.yaml`:

```yaml
analysis:
  # Write a JSON snapshot each successful collect (LaunchAgent should enable this).
  persist_snapshots: true
  # Blend learned burn rates into pace; emit chronic-waste INFO/alerts from history.
  # Implies persist (cli always saves when learning is on).
  learn_from_history: false
  snapshot_retention_days: 90
```

| Flag                 | Default | Effect                                        |
| -------------------- | ------- | --------------------------------------------- |
| `persist_snapshots`  | `false` | Save snapshots only; **no** scoring change    |
| `learn_from_history` | `false` | Use history in analysis; also saves snapshots |

Recommended sequence:

1. Install the LaunchAgent ([`scheduling.md`](scheduling.md)) with
   `persist_snapshots: true`.
2. Wait until `aiuse --full` shows several snapshots (a day or two at hourly cadence).
3. Set `learn_from_history: true`.

## Status line

`aiuse --full` includes:

```text
History: N snapshots in /Users/…/.cache/aiuse/snapshots (learning off|on)
```

## What learning does

When `learn_from_history` is true ([`src/aiuse/analysis/history.py`](../src/aiuse/analysis/history.py)):

- **Learned burn rates** — blend into pace so early-window classification is less noisy
- **Learned flexibility** — light adjustment of flexibility scores
- **Chronic waste** — short windows that stay high-remaining across **multiple**
  reset cycles can surface as history-sourced alerts

Learning needs at least **two** retained snapshots (and meaningful time/usage
deltas). Empty or brand-new caches are inert.

## Scheduling

See [`scheduling.md`](scheduling.md) for the 6-hour LaunchAgent recipe.

## Related

- [`json-contract.md`](json-contract.md) — exit codes for scheduled runs
- [`config/services.example.yaml`](../config/services.example.yaml) — example keys
