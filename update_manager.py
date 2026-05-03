from __future__ import annotations

import datetime as dt
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Iterable, Tuple

BASE_DIR = Path(__file__).resolve().parent
INBOX_DIR = BASE_DIR / "updates" / "inbox"
BACKUP_DIR = BASE_DIR / "updates" / "backups"
STAGE_DIR = BASE_DIR / "updates" / "stage"

PROTECTED_NAMES = {
    ".env",
    "remote_config.json",
    "alarm_state.json",
    "state.json",
}
PROTECTED_DIRS = {
    ".git",
    "venv",
    ".venv",
    "__pycache__",
    "logs",
    "updates",
}

ALLOWED_EXTENSIONS = {
    ".py", ".json", ".txt", ".md", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".bat", ".ps1"
}


def ensure_dirs() -> None:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_DIR.mkdir(parents=True, exist_ok=True)


def _normalized_zip_path(member_name: str) -> Path:
    name = member_name.replace("\\", "/")
    p = Path(name)

    if not name or name.endswith("/"):
        raise ValueError("Boş ZIP yolu")

    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"Güvensiz ZIP yolu reddedildi: {name}")

    return p


def safe_members(zf: zipfile.ZipFile) -> Iterable[tuple[zipfile.ZipInfo, Path]]:
    for member in zf.infolist():
        try:
            rel = _normalized_zip_path(member.filename)
        except ValueError:
            continue

        first = rel.parts[0] if rel.parts else ""
        if first in PROTECTED_DIRS:
            continue
        if rel.name in PROTECTED_NAMES:
            continue
        if rel.suffix.lower() and rel.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue

        yield member, rel


def latest_pending_zip() -> Path | None:
    ensure_dirs()
    zips = sorted(INBOX_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    return zips[0] if zips else None


def make_backup() -> Path:
    ensure_dirs()
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"backup_{stamp}"
    backup_path.mkdir(parents=True, exist_ok=True)

    for item in BASE_DIR.iterdir():
        if item.name in PROTECTED_DIRS:
            continue
        dst = backup_path / item.name
        if item.is_dir():
            shutil.copytree(item, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        elif item.is_file():
            shutil.copy2(item, dst)

    return backup_path


def extract_to_stage(zip_path: Path) -> Path:
    if STAGE_DIR.exists():
        shutil.rmtree(STAGE_DIR)
    STAGE_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        for member, rel in safe_members(zf):
            target = STAGE_DIR / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member, "r") as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)

    return STAGE_DIR


def copy_stage_to_project(stage: Path) -> list[str]:
    changed = []
    for src in stage.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(stage)
        if rel.parts and rel.parts[0] in PROTECTED_DIRS:
            continue
        if rel.name in PROTECTED_NAMES:
            continue
        dst = BASE_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        changed.append(str(rel))
    return changed


def syntax_check() -> Tuple[bool, str]:
    py_files = [
        str(p) for p in BASE_DIR.rglob("*.py")
        if not any(part in PROTECTED_DIRS for part in p.parts)
    ]
    if not py_files:
        return True, "Python dosyası bulunmadı; syntax check atlandı."

    cmd = [sys.executable, "-m", "py_compile"] + py_files
    proc = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True, timeout=90)
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, out.strip() or "Syntax OK"


def latest_backup() -> Path | None:
    ensure_dirs()
    backups = sorted([p for p in BACKUP_DIR.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
    return backups[0] if backups else None


def rollback_from_backup(backup_path: Path) -> str:
    if not backup_path.exists() or not backup_path.is_dir():
        raise FileNotFoundError(f"Backup bulunamadı: {backup_path}")

    for item in BASE_DIR.iterdir():
        if item.name in PROTECTED_DIRS:
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    for item in backup_path.iterdir():
        dst = BASE_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, dst)
        else:
            shutil.copy2(item, dst)

    return f"Rollback tamamlandı: {backup_path.name}"


def rollback() -> str:
    backup = latest_backup()
    if not backup:
        return "Rollback için backup bulunamadı."
    return rollback_from_backup(backup)


def apply_update(zip_path: Path | None = None) -> str:
    ensure_dirs()
    zip_path = zip_path or latest_pending_zip()
    if not zip_path:
        return "Uygulanacak ZIP bulunamadı."

    backup = make_backup()
    try:
        stage = extract_to_stage(zip_path)
        changed = copy_stage_to_project(stage)
        ok, check_output = syntax_check()
        if not ok:
            rollback_from_backup(backup)
            return "❌ Update başarısız. Syntax test geçmedi, rollback yapıldı.\n\n" + check_output[:3000]

        return (
            "✅ Update uygulandı.\n"
            f"Backup: {backup.name}\n"
            f"Değişen dosya sayısı: {len(changed)}"
        )
    except Exception as exc:
        try:
            rollback_from_backup(backup)
        except Exception:
            pass
        return f"❌ Update sırasında hata: {exc}\nRollback denendi."
