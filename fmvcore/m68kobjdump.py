from __future__ import annotations

import itertools
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from fmvcore.writetiming import Gap, Instruction, Listing, Program, gaps

CYCLE_UNIT: Final = "cycles"
BUS_CYCLE: Final = 4
WORD_BYTES: Final = 2
MINIMUM_CYCLES: Final = 4
BRANCH_ALWAYS_CYCLES: Final = 10
BRANCH_CONDITIONAL_CYCLES: Final = 8
DECREMENT_BRANCH_CYCLES: Final = 10
SECTION_SYMBOL: Final = "."
OFFSET_MARK: Final = "+"

UNCONDITIONAL: Final = ("bra", "jra", "jmp")
CALL: Final = ("jsr", "bsr", "jbsr")
BIT_OPERATION: Final = ("bset", "btst", "bclr", "bchg")
RETURN: Final = ("rts", "rtr")
END: Final = ("rts", "rtr", "rte")

CYCLE_TABLE: Final = {
    "moveq": 4, "swap": 4, "extl": 4, "extw": 4, "clrw": 4, "clrl": 6, "tstb": 4,
    "tstw": 4, "tstl": 4, "nop": 4, "addqw": 4, "subqw": 4, "addql": 8, "subql": 8,
    "addiw": 8, "subiw": 8, "andiw": 8, "oriw": 8, "cmpiw": 8, "cmpib": 8, "addil": 16,
    "subil": 16, "andil": 16, "oril": 16, "cmpil": 14, "cmpw": 4, "cmpl": 6, "addw": 4,
    "addl": 8, "orw": 4, "orl": 8, "andw": 4, "andl": 8, "lslw": 6, "lsrw": 6, "lsll": 8,
    "lsrl": 8, "pea": 12, "jsr": 18, "bsrs": 18, "rts": 16,
}  # fmt: skip

LINE = re.compile(r"^\s*([0-9a-f]+):\t([0-9a-f ]+?)\s*(?:\t(.*))?$")
SECTION = re.compile(r"^Disassembly of section (\S+):")
SYMBOL = re.compile(r"^([0-9a-f]{8}) <(.+)>:")
RELOCATION = re.compile(r"^\s+[0-9a-f]+: R_68K_\w+\s+(\S+)$")
PORT_INTO_REGISTER = re.compile(r"^moveal\s+#(\d+),%(a[0-7])$")
ABSOLUTE_WRITE = re.compile(r"^move([lw])\s+(.+?),([0-9a-f]{6})\b")
INDIRECT_WRITE = re.compile(r"^move([lw])\s+(.+?),%(a[0-7])@$")
REGISTER_CLOBBER = re.compile(r",%(a[0-7])\b")
BRANCH_TARGET = re.compile(r"\b([0-9a-f]+)\s+<")
NAMED_TARGET = re.compile(r"<([^>+]+)>$")
PLAIN_REGISTER = re.compile(r"%[da][0-7]")
PLAIN_INDIRECT = re.compile(r"%a[0-7]@")
DISPLACED_INDIRECT = re.compile(r"%a[0-7]@\(-?\d+\)")

Node = tuple[str, int]
Functions = Mapping[str, Mapping[int, str]]


class UnmodelledWriteError(ValueError):
    pass


class UnresolvedCallError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Access:
    kind: str | None
    offset: int


@dataclass(frozen=True, slots=True)
class Reading:
    program: Program
    accesses: Mapping[Node, tuple[Access, ...]]


@dataclass(frozen=True, slots=True)
class Spacing:
    source: str
    to_source: str
    first: Instruction
    second: Instruction
    leaving: Access
    arriving: Access
    cycles: int


@dataclass(frozen=True, slots=True)
class _Raw:
    address: int
    text: str
    relocation: str | None = None

    @property
    def mnemonic(self) -> str:
        return self.text.split()[0] if self.text else ""


@dataclass(frozen=True, slots=True)
class _Section:
    name: str
    rows: tuple[_Raw, ...]
    symbols: tuple[tuple[int, str], ...]


def cycles_for(mnemonic: str) -> int:
    if mnemonic in CYCLE_TABLE:
        return CYCLE_TABLE[mnemonic]
    if mnemonic.startswith(UNCONDITIONAL):
        return BRANCH_ALWAYS_CYCLES
    if mnemonic.startswith("db"):
        return DECREMENT_BRANCH_CYCLES
    if _conditional_branch(mnemonic):
        return BRANCH_CONDITIONAL_CYCLES
    return MINIMUM_CYCLES


def read(objects: Mapping[str, str], *, ports: Mapping[int, str]) -> Reading:
    listings: dict[str, Listing] = {}
    accesses: dict[Node, tuple[Access, ...]] = {}
    for name, text in objects.items():
        sections = _sections(text)
        functions = {s.name: dict(s.symbols) for s in sections}
        for section in sections:
            key = f"{name}:{section.name}"
            listing, found = _listing(key, section, ports, functions)
            listings = {**listings, key: listing}
            accesses = {**accesses, **found}
    return Reading(program=Program(listings=listings, unit=CYCLE_UNIT), accesses=accesses)


def spacings(reading: Reading, *, budget: int | None = None) -> list[Spacing]:
    inner = [
        spacing
        for source, listing in reading.program.listings.items()
        for instruction in listing.instructions
        for spacing in _inner(
            source, instruction, reading.accesses.get((source, instruction.address), ())
        )
    ]
    walked = [_crossing(reading, gap) for gap in gaps(reading.program, budget=budget)]
    return inner + walked


def _inner(source: str, instruction: Instruction, found: tuple[Access, ...]) -> list[Spacing]:
    return [
        Spacing(
            source,
            source,
            instruction,
            instruction,
            leaving,
            arriving,
            arriving.offset - (leaving.offset + BUS_CYCLE),
        )
        for leaving, arriving in itertools.pairwise(found)
    ]


def _crossing(reading: Reading, gap: Gap) -> Spacing:
    leaving = reading.accesses[(gap.source, gap.first.address)][-1]
    arriving = reading.accesses[(gap.to_source, gap.second.address)][0]
    cycles = gap.cycles - (leaving.offset + BUS_CYCLE) + arriving.offset
    return Spacing(gap.source, gap.to_source, gap.first, gap.second, leaving, arriving, cycles)


def _sections(text: str) -> list[_Section]:
    found: list[_Section] = []
    name = ""
    rows: list[_Raw] = []
    symbols: list[tuple[int, str]] = []
    for line in [*text.splitlines(), "Disassembly of section <end>:"]:
        header = SECTION.match(line)
        if header:
            found = [*found, _Section(name, tuple(rows), tuple(symbols))] if rows else found
            name, rows, symbols = header.group(1), [], []
            continue
        rows, symbols = _absorb(line, rows, symbols)
    return found


def _absorb(
    line: str, rows: list[_Raw], symbols: list[tuple[int, str]]
) -> tuple[list[_Raw], list[tuple[int, str]]]:
    named = SYMBOL.match(line)
    if named:
        return rows, [*symbols, (int(named.group(1), 16), named.group(2))]
    relocation = RELOCATION.match(line)
    if relocation and rows:
        last = rows[-1]
        return [*rows[:-1], _Raw(last.address, last.text, relocation.group(1))], symbols
    matched = LINE.match(line)
    if matched and matched.group(3):
        return [*rows, _Raw(int(matched.group(1), 16), matched.group(3).strip())], symbols
    return rows, symbols


def _listing(
    key: str, section: _Section, ports: Mapping[int, str], functions: Functions
) -> tuple[Listing, dict[Node, tuple[Access, ...]]]:
    profiles = _profiles(section.rows, ports)
    instructions = [
        _instruction(key, row, profiles.get(row.address), functions) for row in section.rows
    ]
    owners = [_owner(section.symbols, row.address) for row in section.rows]
    labels = {name: address for address, name in section.symbols}
    found = {(key, address): accesses for address, (_, accesses) in profiles.items()}
    return Listing(instructions=instructions, labels=labels, owners=owners), found


def _profiles(
    rows: tuple[_Raw, ...], ports: Mapping[int, str]
) -> dict[int, tuple[int, tuple[Access, ...]]]:
    held: dict[str, int] = {}
    found: dict[int, tuple[int, tuple[Access, ...]]] = {}
    for row in rows:
        profile = _write(row.text, held, ports)
        if profile is not None:
            found = {**found, row.address: profile}
            continue
        held = _held_after(row, held, ports)
    return found


def _held_after(row: _Raw, held: dict[str, int], ports: Mapping[int, str]) -> dict[str, int]:
    loaded = PORT_INTO_REGISTER.match(row.text)
    if loaded:
        rest = {k: v for k, v in held.items() if k != loaded.group(2)}
        value = int(loaded.group(1))
        return {**rest, loaded.group(2): value} if value in ports else rest
    if row.mnemonic.startswith("movem"):
        return {}
    clobbered = set(REGISTER_CLOBBER.findall(row.text))
    return {k: v for k, v in held.items() if k not in clobbered}


def _write(
    text: str, held: dict[str, int], ports: Mapping[int, str]
) -> tuple[int, tuple[Access, ...]] | None:
    absolute = ABSOLUTE_WRITE.match(text)
    if absolute and int(absolute.group(3), 16) in ports:
        long_move = absolute.group(1) == "l"
        cycles, offsets = _absolute_profile(long_move, absolute.group(2).strip())
        return cycles, _accesses(long_move, int(absolute.group(3), 16), offsets, ports)
    indirect = INDIRECT_WRITE.match(text)
    if indirect and indirect.group(3) in held:
        long_move = indirect.group(1) == "l"
        cycles, offsets = _indirect_profile(long_move, indirect.group(2).strip())
        return cycles, _accesses(long_move, held[indirect.group(3)], offsets, ports)
    return None


def _accesses(
    long_move: bool, port: int, offsets: tuple[int, ...], ports: Mapping[int, str]
) -> tuple[Access, ...]:
    targets = (port, port + WORD_BYTES) if long_move else (port,)
    return tuple(
        Access(ports.get(target), offset) for target, offset in zip(targets, offsets, strict=True)
    )


def _absolute_profile(long_move: bool, source: str) -> tuple[int, tuple[int, ...]]:
    immediate = source.startswith("#")
    register = PLAIN_REGISTER.fullmatch(source) is not None
    indirect = PLAIN_INDIRECT.fullmatch(source) is not None
    if long_move and immediate:
        return 28, (20, 24)
    if long_move and register:
        return 20, (12, 16)
    if not long_move and (immediate or register or indirect):
        return 20, (16,)
    width = "long" if long_move else "word"
    msg = f"{width} absolute write from {source!r}"
    raise UnmodelledWriteError(msg)


def _indirect_profile(long_move: bool, source: str) -> tuple[int, tuple[int, ...]]:
    register = PLAIN_REGISTER.fullmatch(source) is not None
    if long_move and register:
        return 12, (4, 8)
    if not long_move and register:
        return 8, (4,)
    if not long_move and PLAIN_INDIRECT.fullmatch(source):
        return 12, (8,)
    if not long_move and DISPLACED_INDIRECT.fullmatch(source):
        return 16, (12,)
    width = "long" if long_move else "word"
    msg = f"{width} register indirect write from {source!r}"
    raise UnmodelledWriteError(msg)


def _instruction(
    key: str, row: _Raw, profile: tuple[int, tuple[Access, ...]] | None, functions: Functions
) -> Instruction:
    mnemonic = row.mnemonic
    cycles = profile[0] if profile else cycles_for(mnemonic)
    kinds = [access.kind for access in profile[1] if access.kind] if profile else []
    calls = mnemonic.startswith(CALL)
    jumps = mnemonic.startswith(UNCONDITIONAL)
    named = _named(key, row, functions) if calls or jumps else None
    return Instruction(
        address=row.address,
        cycles=cycles,
        text=row.text,
        port=kinds[0] if kinds else None,
        fall_cycles=cycles,
        conditional=_conditional_branch(mnemonic) or mnemonic.startswith("db"),
        leaves=mnemonic.startswith(END) or jumps,
        returns=mnemonic.startswith(RETURN),
        call=named if calls else None,
        jumped=named if jumps and row.relocation else None,
        target=_target(row) if _branches(mnemonic) and not row.relocation else None,
    )


def _named(key: str, row: _Raw, functions: Functions) -> str | None:
    if row.relocation is None:
        named = NAMED_TARGET.search(row.text)
        return named.group(1) if named else None
    if not row.relocation.startswith(SECTION_SYMBOL):
        return row.relocation
    section, _, offset = row.relocation.partition(OFFSET_MARK)
    found = functions.get(section, {}).get(int(offset, 16) if offset else 0)
    if found is None:
        msg = f"{key} 0x{row.address:04X}: no function at {row.relocation}"
        raise UnresolvedCallError(msg)
    return found


def _branches(mnemonic: str) -> bool:
    return mnemonic.startswith(("bra", "jra", "db")) or _conditional_branch(mnemonic)


def _conditional_branch(mnemonic: str) -> bool:
    return mnemonic.startswith("b") and not mnemonic.startswith(("bra", *BIT_OPERATION, *CALL))


def _target(row: _Raw) -> int | None:
    matched = BRANCH_TARGET.search(row.text)
    return int(matched.group(1), 16) if matched else None


def _owner(symbols: tuple[tuple[int, str], ...], address: int) -> str | None:
    found = [name for start, name in symbols if start <= address]
    return found[-1] if found else None
