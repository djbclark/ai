# Snapshot history and learning

`aiuse` can persist each collect under `~/.cache/aiuse/snapshots/` and blend
that history into pace scoring / chronic-waste alerts once enough data exists.

## Config flags

In `~/.config/aiuse/services.yaml`:

```yaml
analysis:
  persist_snapshots: true
  # true | false | auto (default)
  learn_from_history: auto
  snapshot_retention_days: 90
```

| Flag                 | Default | Effect                  |
| -------------------- | ------- | ----------------------- |
| `persist_snapshots`  | `false` | Save snapshots each run |
| `learn_from_history` | `auto`  | See below               |

### `learn_from_history`

| Value   | Behavior                                                               |
| ------- | ---------------------------------------------------------------------- |
| `auto`  | Learn once retained snapshot count ≥ **2** (same floor as the learner) |
| `true`  | Always attempt learning (still no-op if history is empty/thin)         |
| `false` | Never use history for scoring/alerts                                   |

With `auto`, learning turns on by itself as soon as it can be useful — no manual
flip after the LaunchAgent starts filling the cache. Set `false` to keep
persist-only forever.

Learning (when active) also implies snapshot persistence for that run.

## Status line

`aiuse --full` includes:

```text
History: N snapshots in …/snapshots (learning auto/waiting|auto/on|on|off)
```

## What learning does

When active ([`src/aiuse/analysis/history.py`](../src/aiuse/analysis/history.py)):

- **Learned burn rates** — blend into pace so early-window classification is less noisy
- **Learned flexibility** — light adjustment of flexibility scores
- **Chronic waste** — short windows that stay high-remaining across **multiple**
  reset cycles can surface as history-sourced alerts

## Scheduling

See [`scheduling.md`](scheduling.md). Site LaunchAgent enables `persist_snapshots`
and leaves learning on `auto`.

## Related

- [`json-contract.md`](json-contract.md) — exit codes for scheduled runs
- [`config/services.example.yaml`](../config/services.example.yaml) — example keys
