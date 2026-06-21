# MarketRadarAI Deployment

Production runs from `main` with the MarketRadarAI identity:

- GitHub repository: `ahmtakcm/MarketRadarAI`
- Server checkout: `/home/ahmtakcm/MarketRadarAI`
- Systemd unit: `marketradarai.service`
- Service description: `MarketRadarAI scanner service`
- Market-data source: MEXC futures
- Runtime config: `runtime/remote_config.json`
- State and journals: `data/`
- Application log: `logs/app.log`
- System log: `journalctl -u marketradarai.service`

`MEXC` remains a data-source name, not the product identity. The legacy
`mexc-tarama-bot` name is retained only in compatibility and historical log references.

## Production Service Checklist

- Use `deploy/systemd/marketradarai.service` as the canonical unit.
- Keep `WorkingDirectory=/home/ahmtakcm/MarketRadarAI`.
- Run `/home/ahmtakcm/MarketRadarAI/venv/bin/python -u main.py`.
- Use `Restart=on-failure` with a short `RestartSec` delay.
- Send stdout and stderr to journald.
- Use `MARKETRADAR_LOG_LEVEL`; `MEXC_LOG_LEVEL` is supported only as a legacy fallback.
- Keep Telegram credentials outside git.
- Never delete or overwrite `runtime/remote_config.json` during deployment.

## Deploy Flow

1. Merge the reviewed PR into `main`.
2. Confirm the server checkout is clean and on `main`:
   `cd ~/MarketRadarAI && git status --short --branch`
3. Back up runtime state:
   `mkdir -p backups/pre_deploy_$(date -u +%Y%m%dT%H%M%SZ)`
4. Pull with fast-forward only:
   `git pull --ff-only origin main`
5. Run validation:
   `venv/bin/python -m ruff check .`
6. Run tests:
   `venv/bin/python -m pytest`
7. Confirm `runtime/remote_config.json` still exists.
8. Restart:
   `sudo systemctl restart marketradarai.service`
9. Verify:
   `systemctl status marketradarai.service --no-pager`
10. Inspect logs:
    `journalctl -u marketradarai.service -n 120 --no-pager`
11. Confirm `MarketRadarAI startup success` and a completed scan cycle.

## Restart Loop Triage

`Deactivated successfully` means the Python process exited with status 0. It is expected
for an operator stop or duplicate-instance guard, but not during normal daemon operation.

Check:

- `journalctl -u marketradarai.service -n 200 --no-pager`
- `tail -n 200 logs/app.log`
- `pgrep -af MarketRadarAI/main.py`
- `systemctl show marketradarai.service -p Restart -p MainPID -p ExecMainStatus`

Only one MarketRadarAI process should own scanner and Telegram polling. A Telegram 409
`getUpdates` conflict means another process or host is polling with the same bot token.

## Legacy Compatibility

The migration from these names is complete:

- Old service: `mexc-tarama-bot.service`
- Old path: `/home/ahmtakcm/mexc-tarama-bot`
- Old repository: `ahmtakcm/mexc-tarama-bot`

The repo keeps `deploy/systemd/mexc-tarama-bot.service.compat` only as a rollback reference.
The old production unit should remain disabled and should not be started alongside
`marketradarai.service`.

Historical journald entries remain available with:

- `journalctl -u mexc-tarama-bot.service`
- `journalctl -u marketradarai.service`

## Rollback

1. Stop `marketradarai.service`.
2. Revert the deployment through a reviewed git revert on `main`.
3. Preserve `runtime/remote_config.json`, `data/state.json`, and all journals.
4. Restore runtime files from the pre-deploy checkpoint only if they are missing or corrupt.
5. Start `marketradarai.service` and repeat the health checks.

Do not reactivate the legacy service unless a verified rollback procedure explicitly requires it.

## Manual Identity Checks

- Confirm the Telegram BotFather display name is `MarketRadarAI`.
- Confirm Telegram help/status/watchlist messages start with `MarketRadarAI`.
- Keep `MEXC` visible only where the active exchange or data source is being described.
