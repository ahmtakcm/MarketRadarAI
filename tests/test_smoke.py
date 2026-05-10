from pathlib import Path


def test_project_entrypoint_exists():
    assert Path("main.py").is_file()


def test_requirements_file_exists():
    assert Path("requirements.txt").is_file()
