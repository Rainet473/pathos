from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPOSITORY_ROOT / "scripts" / "run-frontend.sh"


def _copy_launcher(destination: Path) -> Path:
    scripts = destination / "scripts"
    scripts.mkdir()
    copied = scripts / "run-frontend.sh"
    shutil.copy2(LAUNCHER, copied)
    return copied


@pytest.mark.offline
def test_launcher_runs_checked_in_frontend_and_forwards_vite_arguments_from_any_cwd(
    tmp_path: Path,
):
    assert LAUNCHER.is_file()
    assert LAUNCHER.stat().st_mode & stat.S_IXUSR

    project = tmp_path / "project"
    project.mkdir()
    launcher = _copy_launcher(project)
    frontend = project / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text("{}\n", encoding="utf-8")
    (frontend / "node_modules").mkdir()
    capture = tmp_path / "capture"
    capture.mkdir()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_npm = fake_bin / "npm"
    fake_npm.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$@\" > \"$FRONTEND_LAUNCH_CAPTURE/arguments\"\n"
        "pwd > \"$FRONTEND_LAUNCH_CAPTURE/working-directory\"\n",
        encoding="utf-8",
    )
    fake_npm.chmod(0o755)

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    environment["FRONTEND_LAUNCH_CAPTURE"] = str(capture)
    environment["CONDA_PREFIX"] = "/test/active-conda-environment"

    completed = subprocess.run(
        [str(launcher), "--host", "0.0.0.0"],
        cwd=elsewhere,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert (capture / "working-directory").read_text(encoding="utf-8").strip() == str(
        frontend
    )
    assert (capture / "arguments").read_text(encoding="utf-8").splitlines() == [
        "run",
        "dev",
        "--",
        "--host",
        "0.0.0.0",
    ]


@pytest.mark.offline
def test_launcher_fails_clearly_when_frontend_dependencies_are_missing(
    tmp_path: Path,
):
    project = tmp_path / "project"
    project.mkdir()
    launcher = _copy_launcher(project)
    frontend = project / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text("{}\n", encoding="utf-8")

    completed = subprocess.run(
        [str(launcher)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "Frontend dependencies are missing" in completed.stderr
    assert "npm ci" in completed.stderr


@pytest.mark.offline
def test_launcher_fails_clearly_without_an_active_conda_environment(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    launcher = _copy_launcher(project)
    frontend = project / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text("{}\n", encoding="utf-8")
    (frontend / "node_modules").mkdir()
    environment = os.environ.copy()
    environment.pop("CONDA_PREFIX", None)

    completed = subprocess.run(
        [str(launcher)],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "No active conda environment" in completed.stderr
