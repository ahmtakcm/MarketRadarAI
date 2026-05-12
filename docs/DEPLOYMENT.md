# MarketRadarAI Deployment

This repository currently runs in production from `main` under the legacy service name
`mexc-tarama-bot.service` and legacy server path `~/mexc-tarama-bot`. The visible product
identity is MarketRadarAI. The rename must be applied manually in production after this PR is merged.

## Production Service Checklist

- Service name: `mexc-tarama-bot.service`
- Recommended description: `MarketRadarAI scanner service`
- Repo-managed target unit: `deploy/systemd/marketradarai.service`
- Repo-managed compatibility unit: `deploy/systemd/mexc-tarama-bot.service.compat`
- WorkingDirectory: production checkout path, usually the server `mexc-tarama-bot` directory
- ExecStart: project virtualenv or Python interpreter running `main.py`
- Restart policy: prefer `Restart=on-failure`. Avoid `Restart=always` unless intentionally running one-shot jobs.
- RestartSec: keep a small delay, for example `RestartSec=5`
- StandardOutput: `journal`
- StandardError: `journal`
- Environment: `MEXC_LOG_LEVEL=INFO` unless debugging
- Environment: `MARKETRADAR_RUNTIME_CONFIG=/absolute/path/to/runtime/remote_config.json` when overriding the default
- Runtime config: `runtime/remote_config.json`
- App log: `logs/app.log`; the same application log stream is also written to stderr for journald capture.
- System log: `journalctl -u mexc-tarama-bot.service`

## Deploy Flow

1. Merge reviewed PR into `main`.
2. On the server, verify current branch is `main`.
3. Pull latest `main`.
4. Run `ruff check .`.
5. Run `pytest`.
6. Verify `runtime/remote_config.json` exists and preserves production overrides.
7. Restart `mexc-tarama-bot.service`.
8. Check `systemctl status mexc-tarama-bot.service`.
9. Check `journalctl -u mexc-tarama-bot.service -n 120 --no-pager`.
10. Confirm `logs/app.log` contains `MarketRadarAI startup` and `MarketRadarAI startup success`.
11. Confirm startup logs include `MarketRadarAI asset universe` with supported and unsupported counts.

## Restart Loop Triage

Past production observations included a high systemd restart counter and `Deactivated successfully`.
That message means the Python process exited cleanly with status 0, not that systemd saw a crash.
MarketRadarAI is designed as a long-running daemon from `main.py`; a clean exit is expected only for
operator shutdown, duplicate-instance guard exit, or a service command that starts the wrong process.

If the unit uses `Restart=always`, systemd will restart even clean exits. That can turn duplicate
instance guard exits into a restart counter loop. Prefer `Restart=on-failure` for this daemon so
clean exits stay stopped while real crashes still restart.

Check these first:

- `journalctl -u mexc-tarama-bot.service -n 200 --no-pager`
- `journalctl -u mexc-tarama-bot.service --since "1 hour ago" --no-pager`
- `tail -n 200 logs/app.log`
- `grep -i "fatal crash\|startup\|scan start\|scan finish\|force_scan_once" logs/app.log`

The app now logs:

- startup metadata: exchange, active modes, watchlist count, state path, runtime config path
- asset universe summary: requested, supported, and unsupported watchlist counts
- startup success after symbols are loaded and watchlist filtering is applied
- scan loop start and finish, including active modes and symbol count
- `/scan_now` flag consumption with active modes and watchlist count
- duplicate-instance guard exits, including the lock path
- fatal crash visibility before process exit
- KeyboardInterrupt shutdown visibility

Application logs are written to both `logs/app.log` and stderr. With `StandardError=journal`, the
same startup, scan, shutdown, and fatal-crash lines should be visible in `journalctl`.

## Safe Service Rename Plan

Do not rename the systemd unit automatically in this PR. Apply the following steps manually on the server.

Target:

- Old service: `mexc-tarama-bot.service`
- New service: `marketradarai.service`
- Old path: `/home/ahmtakcm/mexc-tarama-bot`
- New path: `/home/ahmtakcm/MarketRadarAI`
- Old GitHub remote: `ahmtakcm/mexc-tarama-bot`
- Future GitHub remote: `ahmtakcm/MarketRadarAI`

### Preflight

1. Confirm current production is healthy:
   `sudo systemctl status mexc-tarama-bot.service`
2. Confirm current logs:
   `journalctl -u mexc-tarama-bot.service -n 120 --no-pager`
3. Confirm working tree on server:
   `cd ~/mexc-tarama-bot && git status --short --branch`
4. Confirm tests on `main`:
   `ruff check . && pytest`
5. Back up runtime config:
   `mkdir -p ~/marketradarai-migration-backup && cp runtime/remote_config.json ~/marketradarai-migration-backup/remote_config.json.$(date +%Y%m%d%H%M%S)`

### Path And Remote Rename

1. Stop the old service:
   `sudo systemctl stop mexc-tarama-bot.service`
2. Rename the directory:
   `mv ~/mexc-tarama-bot ~/MarketRadarAI`
3. Enter the new directory:
   `cd ~/MarketRadarAI`
4. If the GitHub repository has already been renamed, update remote:
   `git remote set-url origin git@github.com:ahmtakcm/MarketRadarAI.git`
5. If the GitHub repository has not been renamed yet, keep the old remote temporarily:
   `git remote -v`
6. Verify branch and files:
   `git status --short --branch`

### Unit Rename

1. Copy the repo-managed target unit:
   `sudo cp deploy/systemd/marketradarai.service /etc/systemd/system/marketradarai.service`
2. Verify or edit paths in the unit:
   `sudo systemctl cat marketradarai.service`
3. Reload systemd:
   `sudo systemctl daemon-reload`
4. Start the new service:
   `sudo systemctl start marketradarai.service`
5. Validate:
   `sudo systemctl status marketradarai.service`
6. Validate new journal:
   `journalctl -u marketradarai.service -n 120 --no-pager`
7. Validate app log continuity:
   `tail -n 120 logs/app.log`
8. Telegram smoke test: `/help`, `/status`, `/watchlist`, `/scan_now`.
9. Disable old service only after validation:
   `sudo systemctl disable mexc-tarama-bot.service`

## Repo And Path Rename Plan

Repository and server path rename are prepared by this PR but not applied automatically.

Future low-risk migration:

1. Rename GitHub repository after all active PRs are merged.
2. Update local/server git remotes with the new GitHub URL.
3. Create or move the server directory to the target MarketRadarAI path.
4. Keep the old `mexc-tarama-bot` directory until the new service is validated.
5. Update systemd `WorkingDirectory` and `ExecStart`.
6. Run `systemctl daemon-reload`.
7. Start the new service and confirm journal continuity.
8. Roll back by stopping the new service and starting `mexc-tarama-bot.service` from the old path.

## Rollback

If the new service fails:

1. Stop the new unit:
   `sudo systemctl stop marketradarai.service`
2. Re-enable or start the old unit:
   `sudo systemctl start mexc-tarama-bot.service`
3. If the directory was renamed and old unit paths are still legacy paths, move it back:
   `mv ~/MarketRadarAI ~/mexc-tarama-bot`
4. Reload systemd if units were edited:
   `sudo systemctl daemon-reload`
5. Validate old service:
   `sudo systemctl status mexc-tarama-bot.service`
6. Check old journal:
   `journalctl -u mexc-tarama-bot.service -n 120 --no-pager`

Rollback must not delete `runtime/remote_config.json`. Restore it only from the preflight backup if the file is missing or corrupt.

## Journal And Log Continuity

Systemd journals are unit-name scoped. After rename, old logs remain under:

- `journalctl -u mexc-tarama-bot.service`

New logs appear under:

- `journalctl -u marketradarai.service`

Application file logs remain in the project path:

- old path: `/home/ahmtakcm/mexc-tarama-bot/logs/app.log`
- new path: `/home/ahmtakcm/MarketRadarAI/logs/app.log`

If the directory is moved rather than freshly cloned, file log continuity is preserved in the moved `logs/` directory.

## Deferred

- Rename the systemd unit.
- Rename server directory or repository.
- Change Telegram bot display name or username.
- Move polling ownership out of `main.py`.
- Change scanner or exchange adapter architecture.
