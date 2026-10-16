from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path


def copy_files(names: tuple[str, ...], source: Path, target: Path, *, required: bool) -> list[Path]:
    missing = [name for name in names if not (source / name).is_file()]
    if required and missing:
        msg = f"the bundle needs {missing[0]}, which is not in {source}"
        raise FileNotFoundError(msg)
    present = [name for name in names if name not in missing]
    target.mkdir(parents=True, exist_ok=True)
    return [Path(shutil.copy2(source / name, target / name)) for name in present]


def render(template: Path, fields: Mapping[str, object]) -> str:
    return template.read_text(encoding="utf-8").format(**fields)
