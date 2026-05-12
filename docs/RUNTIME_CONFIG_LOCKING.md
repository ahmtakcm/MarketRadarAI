# Runtime Config Locking

MarketRadarAI stores mutable runtime/user config in `runtime/remote_config.json`.
The tracked root `remote_config.json` is only a legacy seed and must not be used as the active mutable config.

## What Is Protected

Runtime config writes use:

- `runtime/remote_config.lock` for cross-process write serialization.
- Atomic temporary-file write and replace for partial-write protection.
- Schema migration before every saved payload.

This protects read-modify-write paths where two actors might otherwise load the same old config and overwrite each other.

Examples:

- `/scan_now` sets `runtime.force_scan_once = true`.
- `ScannerRuntime` consumes and clears `runtime.force_scan_once`.
- `/add_symbol` and `/remove_symbol` update `watchlist.symbols`.
- Mode and filter commands update runtime control fields.

## Caller Rule

Use `remote_config.update_config(mutator)` for any read-modify-write operation.

Do not write new code that does this:

```python
cfg = load_config()
cfg["runtime"]["force_scan_once"] = True
save_config(cfg)
```

Use this instead:

```python
def mutate(cfg):
    cfg.setdefault("runtime", {})["force_scan_once"] = True

update_config(mutate)
```

`load_config()` remains valid for read-only paths. `save_config()` remains available for full replacement writes and still uses the same file lock.

## Recovery

If `runtime/remote_config.json` is corrupt, it is archived to `runtime/remote_config.json.broken` and recreated from defaults.
If the runtime file is missing, the legacy root `remote_config.json` can seed the runtime file once.

## Deployment Check

After deploy:

```bash
git status --short
python -m pytest
journalctl -u mexc-tarama-bot.service -n 80 --no-pager
```

Expected:

- `remote_config.json` remains clean.
- `runtime/remote_config.json` remains ignored.
- `/scan_now` still sets and consumes `runtime.force_scan_once`.
- `/add_symbol` and `/remove_symbol` preserve unrelated config fields.

## Rollback

Revert the PR to restore the previous atomic-write-only behavior.
Do not delete `runtime/remote_config.json` during rollback unless you have a current manual backup.
