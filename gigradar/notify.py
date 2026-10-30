"""Desktop notifications — best-effort, cross-platform, no hard dependency.

Order of preference: ``notify-send`` (Linux), ``osascript`` (macOS),
``powershell`` toast (Windows). If none work, we silently no-op so the tool
never crashes just because notifications aren't available.
"""

from __future__ import annotations

import platform
import shutil
import subprocess


def notify(title: str, message: str) -> bool:
    system = platform.system()
    try:
        if system == "Linux" and shutil.which("notify-send"):
            subprocess.run(
                ["notify-send", "-a", "GigRadar", title, message],
                check=False,
                timeout=5,
            )
            return True
        if system == "Darwin" and shutil.which("osascript"):
            safe_msg = message.replace('"', "'")
            safe_title = title.replace('"', "'")
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{safe_msg}" with title "{safe_title}"'],
                check=False,
                timeout=5,
            )
            return True
        if system == "Windows" and shutil.which("powershell"):
            script = (
                "powershell -NoProfile -Command \""
                "Add-Type -AssemblyName System.Windows.Forms;"
                "$n=New-Object System.Windows.Forms.NotifyIcon;"
                "$n.Icon=[System.Drawing.SystemIcons]::Information;"
                "$n.Visible=$true;"
                f"$n.ShowBalloonTip(5000,'{title}','{message}',"
                "[System.Windows.Forms.ToolTipIcon]::Info)\""
            )
            subprocess.run(script, shell=True, check=False, timeout=5)
            return True
    except Exception:
        return False
    return False
