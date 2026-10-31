"""Create an unpacked-extension ZIP; no Node, Python or build step needed to use it."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import json


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    directory = root / "chrome-extension"
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    required = ["popup.html", "popup.css", "popup.js", "core.js", "webk.js", "main.js", "content.js"]
    assert manifest["manifest_version"] == 3
    for name in required:
        assert (directory / name).is_file(), name
    (root / "dist").mkdir(exist_ok=True)
    output = root / "dist" / "AutoClap-Chrome.zip"
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for file in sorted(directory.rglob("*")):
            if file.is_file() and file.suffix in {".js", ".html", ".css", ".json", ".md", ".png"}:
                archive.write(file, Path("AutoClap-Chrome") / file.relative_to(directory))
    print(output)


if __name__ == "__main__":
    main()
