from pathlib import Path


def test_project_entrypoint_exists():
    assert Path("main.py").is_file()


def test_requirements_file_exists():
    assert Path("requirements.txt").is_file()


def test_marketradarai_runtime_docs_exist():
    assert Path("docs/ASSET_UNIVERSE.md").is_file()
    assert Path("docs/RUNTIME_BEHAVIOR.md").is_file()
    assert Path("docs/SCANNER_ORCHESTRATION.md").is_file()
    assert Path("docs/MARKET_DATA_SERVICE.md").is_file()
    assert Path("docs/SIGNAL_LIFECYCLE.md").is_file()
    assert Path("docs/TELEGRAM_RUNTIME.md").is_file()


def test_systemd_template_exists():
    assert Path("deploy/systemd/marketradarai.service.example").is_file()
