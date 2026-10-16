from __future__ import annotations

from collections.abc import Callable


def first_fit(count: int, fits: Callable[[int], bool]) -> int | None:
    if count < 0:
        msg = f"a ladder cannot have {count} rungs"
        raise ValueError(msg)
    low, high = _bracket(count, fits)
    while low < high:
        middle = (low + high) // 2
        if fits(middle):
            high = middle
        else:
            low = middle + 1
    return low if low < count else None


def _bracket(count: int, fits: Callable[[int], bool]) -> tuple[int, int]:
    if count == 0 or fits(0):
        return 0, 0
    passed = 0
    stride = 1
    for _ in range(count.bit_length()):
        if stride >= count:
            break
        if fits(stride):
            return passed + 1, stride
        passed = stride
        stride *= 2
    return passed + 1, count
