"""Build on the target OS: python scripts/build.py."""

import os
from pathlib import Path
import shutil
import subprocess
import sys


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    arguments = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
        "--onedir", "--name", "AutoClap", "--noupx",
        "--exclude-module", "PySide6.QtQml",
        "--exclude-module", "PySide6.QtQuick",
        "--exclude-module", "PySide6.QtWebEngineCore",
        "--exclude-module", "PySide6.QtWebEngineWidgets",
    ]
    if sys.platform == "darwin":
        arguments += ["--osx-bundle-identifier", "local.autoclap.desktop"]
    subprocess.run(arguments + [str(root / "run.py")], cwd=root, check=True)
    output = root / "dist"
    if sys.platform == "darwin":
        # ditto retains app symlinks and executable permissions.
        archive = output / f"AutoClap-macOS-{os.uname().machine}.zip"
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
                        str(output / "AutoClap.app"), str(archive)], check=True)
    else:
        platform_name = "Windows" if os.name == "nt" else "Linux"
        archive = Path(shutil.make_archive(str(output / f"AutoClap-{platform_name}"), "zip",
                                           root_dir=output, base_dir="AutoClap"))
    print(f"\nBuilt: {archive}")


if __name__ == "__main__":
    main()
