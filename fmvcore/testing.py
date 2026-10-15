from __future__ import annotations

import os
import shutil
from typing import Final, Protocol

import pytest
from faker import Faker

SEED: Final = 20261015
REQUIRED: Final = "1"


class Marked(Protocol):
    def get_closest_marker(self, name: str, /) -> object | None: ...


def seeded() -> Faker:
    fake = Faker()
    fake.seed_instance(SEED)
    return fake


def require_tools(item: Marked, *, marker: str, tools: tuple[str, ...], required_env: str) -> None:
    if item.get_closest_marker(marker) is None:
        return
    missing = [tool for tool in tools if shutil.which(tool) is None]
    if not missing:
        return
    reason = f"{', '.join(missing)} not on the path, and this test needs it"
    if os.environ.get(required_env) == REQUIRED:
        pytest.fail(reason)
    pytest.skip(reason)
