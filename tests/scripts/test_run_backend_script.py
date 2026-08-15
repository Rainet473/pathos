from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPOSITORY_ROOT / "scripts" / "run-backend.sh"


def _copy_launcher(destination: Path) -> Path:
    scripts = destination / "scripts"
    scripts.mkdir()
    copied = scripts / "run-backend.sh"
    shutil.copy2(LAUNCHER, copied)
    return copied


@pytest.mark.offline
def test_launcher_loads_env_and_invokes_expected_uvicorn_command_from_any_cwd(
    tmp_path: Path,
):
    assert LAUNCHER.is_file()
    assert LAUNCHER.stat().st_mode & stat.S_IXUSR

    project = tmp_path / "project"
    project.mkdir()
    launcher = _copy_launcher(project)
    (project / ".env").write_text(
        "LIVEKIT_URL=wss://test.invalid\n"
        "LIVEKIT_API_KEY=test-key\n"
        "LIVEKIT_API_SECRET=test-secret\n",
        encoding="utf-8",
    )
    capture = tmp_path / "capture"
    capture.mkdir()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_uvicorn = fake_bin / "uvicorn"
    fake_uvicorn.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"$@\" > \"$BACKEND_LAUNCH_CAPTURE/arguments\"\n"
        "printf '%s\\n' \"$LIVEKIT_URL\" > \"$BACKEND_LAUNCH_CAPTURE/livekit-url\"\n",
        encoding="utf-8",
    )
    fake_uvicorn.chmod(0o755)

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    environment["BACKEND_LAUNCH_CAPTURE"] = str(capture)
    environment["CONDA_PREFIX"] = "/test/active-conda-environment"

    completed = subprocess.run(
        [str(launcher), "--log-level", "debug"],
        cwd=elsewhere,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert (capture / "livekit-url").read_text(encoding="utf-8").strip() == (
        "wss://test.invalid"
    )
    assert (capture / "arguments").read_text(encoding="utf-8").splitlines() == [
        "voice_presentation.server.app:create_configured_app",
        "--factory",
        "--app-dir",
        str(project / "backend" / "src"),
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--reload",
        "--log-level",
        "debug",
    ]


@pytest.mark.offline
def test_launcher_fails_clearly_when_env_file_is_missing(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    launcher = _copy_launcher(project)

    completed = subprocess.run(
        [str(launcher)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert ".env file not found" in completed.stderr


@pytest.mark.offline
def test_launcher_fails_clearly_without_an_active_conda_environment(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    launcher = _copy_launcher(project)
    (project / ".env").write_text("LIVEKIT_URL=wss://test.invalid\n", encoding="utf-8")
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
