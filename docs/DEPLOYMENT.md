# MarketRadarAI Deployment

This repository currently runs in production from `main` under the existing service name
`mexc-tarama-bot.service`. The repository path may remain `mexc-tarama-bot`; the visible
product identity is MarketRadarAI.

## Production Service Checklist

- Service name: `mexc-tarama-bot.service`
- Recommended description: `MarketRadarAI scanner service`
- WorkingDirectory: production checkout path, usually the server `mexc-tarama-bot` directory
- ExecStart: project virtualenv or Python interpreter running `main.py`
- Restart policy: `Restart=always` or `Restart=on-failure`, depending on current server policy
- RestartSec: keep a small delay, for example `RestartSec=5`
- Environment:
- `MEXC_LOG_LEVEL=INFO` unless debugging
- `MARKETRADAR_RUNTIME_CONFIG=/absolute/path/to/runtime/remote_config.json` when overriding the default
- Runtime config: `runtime/remote_config.json`
- App log: `logs/app.log`
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

## Restart Loop Triage

Past production observations included a high systemd restart counter. This PR does not try to
change restart policy or scanner behavior. It improves visibility so the next incident has a
clearer trail.

Check these first:

- `journalctl -u mexc-tarama-bot.service -n 200 --no-pager`
- `journalctl -u mexc-tarama-bot.service --since "1 hour ago" --no-pager`
- `tail -n 200 logs/app.log`
- `grep -i "fatal crash\|startup\|scan start\|scan finish\|force_scan_once" logs/app.log`

The app now logs:

- startup metadata: exchange, active modes, watchlist count, state path, runtime config path
- startup success after symbols are loaded and watchlist filtering is applied
- scan loop start and finish, including active modes and symbol count
- `/scan_now` flag consumption with active modes and watchlist count
- fatal crash visibility before process exit
- KeyboardInterrupt shutdown visibility

## Safe Service Rename Plan

Do not rename the systemd unit in this PR.

Future low-risk migration:

1. Add a new `marketradarai.service` unit with the same `WorkingDirectory`, `ExecStart`, environment, and restart policy.
2. Stop but do not disable `mexc-tarama-bot.service`.
3. Start `marketradarai.service`.
4. Validate logs and Telegram behavior.
5. Disable the old service only after validation.
6. Keep rollback instructions to re-enable `mexc-tarama-bot.service`.

## Deferred

- Rename the systemd unit.
- Rename server directory or repository.
- Change Telegram bot display name or username.
- Move polling ownership out of `main.py`.
- Change scanner or exchange adapter architecture.
