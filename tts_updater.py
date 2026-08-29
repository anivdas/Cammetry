from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class UpdateInfo:
    current_version: str
    latest_version: str
    html_url: str
    setup_url: str = ""
    setup_name: str = ""


def _version_tuple(value: str) -> tuple[int, ...]:
    match = re.search(r"(\d+(?:\.\d+)+)", str(value))
    if not match:
        return (0,)
    return tuple(int(part) for part in match.group(1).split("."))


def is_newer(latest: str, current: str) -> bool:
    a = list(_version_tuple(latest))
    b = list(_version_tuple(current))
    width = max(len(a), len(b))
    a.extend([0] * (width - len(a)))
    b.extend([0] * (width - len(b)))
    return tuple(a) > tuple(b)


def fetch_latest_release(repo: str, current_version: str, timeout: int = 8) -> Optional[UpdateInfo]:
    repo = repo.strip().strip("/")
    if not repo or "/" not in repo:
        raise ValueError("Invalid GitHub update repository.")
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Cammetry-Updater",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    tag = str(payload.get("tag_name") or "").lstrip("vV")
    if not tag or not is_newer(tag, current_version):
        return None
    setup_url = ""
    setup_name = ""
    if os.name == "nt":
        for asset in payload.get("assets") or []:
            name = str(asset.get("name") or "")
            lower = name.lower()
            if lower.startswith("cammetry-setup-v") and lower.endswith(".exe"):
                setup_url = str(asset.get("browser_download_url") or "")
                setup_name = name
                break
    return UpdateInfo(
        current_version=current_version,
        latest_version=tag,
        html_url=str(payload.get("html_url") or f"https://github.com/{repo}/releases/latest"),
        setup_url=setup_url,
        setup_name=setup_name,
    )


def download_setup(info: UpdateInfo, destination_dir: Path, timeout: int = 60) -> Path:
    if not info.setup_url or not info.setup_name:
        raise RuntimeError("This release does not contain a Windows Setup installer.")
    destination_dir.mkdir(parents=True, exist_ok=True)
    output = destination_dir / info.setup_name
    request = urllib.request.Request(info.setup_url, headers={"User-Agent": "Cammetry-Updater"})
    with urllib.request.urlopen(request, timeout=timeout) as response, output.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    if output.stat().st_size < 1024 * 1024:
        output.unlink(missing_ok=True)
        raise RuntimeError("Downloaded installer is unexpectedly small.")
    return output


def authenticode_is_trusted(path: Path) -> bool:
    if os.name != "nt":
        return False
    command = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        f"$s=Get-AuthenticodeSignature -LiteralPath '{str(path).replace("'", "''")}'; if ($s.Status -eq 'Valid') {{ exit 0 }} else {{ Write-Output $s.Status; exit 1 }}",
    ]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.returncode == 0
    except Exception:
        return False


def schedule_windows_install_on_exit(installer: Path, current_pid: int, relaunch_path: Optional[Path] = None) -> None:
    if os.name != "nt":
        raise RuntimeError("Automatic installation is currently supported on Windows only.")
    quoted_installer = str(installer).replace("'", "''")
    relaunch = str(relaunch_path or Path(sys.executable)).replace("'", "''")
    script = (
        f"Wait-Process -Id {int(current_pid)} -ErrorAction SilentlyContinue; "
        f"$p=Start-Process -FilePath '{quoted_installer}' -ArgumentList '/S' -Verb RunAs -Wait -PassThru; "
        f"if ($p.ExitCode -eq 0 -and (Test-Path -LiteralPath '{relaunch}')) {{ Start-Process -FilePath '{relaunch}' }}"
    )
    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )
