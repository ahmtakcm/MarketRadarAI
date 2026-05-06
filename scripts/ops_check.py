import argparse
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SERVICES = ("mexc-tarama-bot.service", "mexc-telegram-commands.service")
OLD_SERVICE = "riskradarai.service"
OLD_PROCESS_MARKER = "/RiskRadarAI/"
MAIN_PROCESS_MARKER = "/mexc-tarama-bot/main.py"
TELEGRAM_PROCESS_MARKER = "/mexc-tarama-bot/telegram_remote.py"


def run_command(args):
    try:
        completed = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True, timeout=10)
    except FileNotFoundError:
        return None, "missing command"
    except subprocess.TimeoutExpired:
        return None, "timeout"

    output = (completed.stdout or "").strip()
    error = (completed.stderr or "").strip()
    return completed.returncode, output or error


def print_result(ok, name, detail):
    status = "OK" if ok else "FAIL"
    print(f"{status} {name}: {detail}")
    return ok


def process_lines():
    if sys.platform.startswith("win"):
        code, output = run_command(["wmic", "process", "get", "CommandLine"])
    else:
        code, output = run_command(["ps", "aux"])

    if code != 0 or not output:
        return []

    return [line for line in output.splitlines() if line.strip()]


def count_processes(lines, marker):
    normalized_marker = marker.replace("/", "\\") if sys.platform.startswith("win") else marker
    return sum(1 for line in lines if normalized_marker in line)


def check_processes():
    lines = process_lines()
    if not lines:
        return print_result(False, "process_check", "process list could not be read")

    old_count = count_processes(lines, OLD_PROCESS_MARKER)
    main_count = count_processes(lines, MAIN_PROCESS_MARKER)
    telegram_count = count_processes(lines, TELEGRAM_PROCESS_MARKER)

    ok = True
    ok &= print_result(old_count == 0, "old_riskradarai_process", f"count={old_count}")
    ok &= print_result(main_count == 1, "main_process", f"count={main_count}")
    ok &= print_result(telegram_count == 1, "telegram_remote_process", f"count={telegram_count}")
    return ok


def systemctl_available():
    return shutil.which("systemctl") is not None


def check_service_active(service):
    code, output = run_command(["systemctl", "is-active", service])
    return code == 0 and output == "active", output or "unknown"


def check_service_enabled(service):
    code, output = run_command(["systemctl", "is-enabled", service])
    return code == 0 and output == "enabled", output or "unknown"


def check_services():
    if not systemctl_available():
        print("SKIP systemd_services: systemctl not available")
        return True

    ok = True
    for service in EXPECTED_SERVICES:
        active, active_detail = check_service_active(service)
        enabled, enabled_detail = check_service_enabled(service)
        ok &= print_result(active, f"{service}_active", active_detail)
        ok &= print_result(enabled, f"{service}_enabled", enabled_detail)

    old_active, old_active_detail = check_service_active(OLD_SERVICE)
    old_enabled, old_enabled_detail = check_service_enabled(OLD_SERVICE)
    ok &= print_result(not old_active, f"{OLD_SERVICE}_active", old_active_detail)
    ok &= print_result(not old_enabled, f"{OLD_SERVICE}_enabled", old_enabled_detail)
    return ok


def check_git_status():
    code, output = run_command(["git", "status", "--short"])
    if code != 0:
        return print_result(False, "git_status", output or "unavailable")

    lines = [line for line in output.splitlines() if line.strip()]
    unexpected = [line for line in lines if "remote_config.json" not in line]
    remote_modified = [line for line in lines if "remote_config.json" in line]

    if remote_modified:
        print_result(True, "remote_config_runtime_modified", "; ".join(remote_modified))

    if unexpected:
        return print_result(False, "git_unexpected_changes", "; ".join(unexpected))

    return print_result(True, "git_unexpected_changes", "none")


def check_required_files():
    required = [
        "main.py",
        "telegram_remote.py",
        "telegram_commands.py",
        "telegram/router.py",
        "telegram/read_commands.py",
        "telegram/watchlist_commands.py",
        "remote_config.py",
    ]
    missing = [path for path in required if not (REPO_ROOT / path).exists()]
    return print_result(not missing, "required_files", "ok" if not missing else ", ".join(missing))


def main():
    parser = argparse.ArgumentParser(description="Check MEXC bot operational process and service state.")
    parser.add_argument("--skip-process", action="store_true", help="Skip process count checks.")
    parser.add_argument("--skip-services", action="store_true", help="Skip systemd service checks.")
    args = parser.parse_args()

    ok = True
    ok &= check_required_files()
    ok &= check_git_status()

    if not args.skip_process:
        ok &= check_processes()

    if not args.skip_services:
        ok &= check_services()

    print(f"ops_check={'ok' if ok else 'failed'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
