from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Final

from fmvcore.writetiming import Instruction, Listing

CYCLE_UNIT: Final = "T-states"
REPEAT_INTERVAL: Final = 21
PORT_MASK: Final = 0xFF
NOT_TAKEN_CYCLES: Final = {"jr": 7, "djnz": 8, "call": 10, "ret": 5}
FUNCTION_PREFIX: Final = "_"
LOCAL_SUFFIX: Final = "$"
GLOBAL_MARK: Final = ":"

CODE = re.compile(
    r"^\s*([0-9A-Fa-f]{8})\s+((?:[0-9A-Fa-fr]{2}\s?)+?)\s+\[\s*(\d+)\s*\]\s+\d+\s+(.*?)\s*$"
)
LABEL = re.compile(r"^\s*([0-9A-Fa-f]{8})\s+\d+\s+(\S+):\s*$")
BRANCH = re.compile(r"^(jp|jr|djnz)\b\s*(?:([A-Za-z]+)\s*,\s*)?(\S+)\s*$")
CALL = re.compile(r"^call\b\s*(?:([A-Za-z]+)\s*,\s*)?(\S+)\s*$")
UNCONDITIONAL_END = re.compile(r"^(ret|reti|retn)\b")
PORT_IMMEDIATE = re.compile(r"^out\s*\(\s*#?(0x[0-9A-Fa-f]+|\d+)\s*\)\s*,")
PORT_REGISTER = re.compile(r"^out\s*\(\s*c\s*\)\s*,")
BLOCK_OUTPUT = re.compile(r"^(outi|outd|otir|otdr)\b")
REPEATING_OUTPUT = re.compile(r"^(otir|otdr)\b")
LOAD_C = re.compile(r"^ld\s+c\s*,\s*#?(0x[0-9A-Fa-f]+|\d+)\s*$")
CLOBBER_C = re.compile(
    r"^(ld\s+(c|bc)\s*,|pop\s+bc\b|inc\s+(c|bc)\b|dec\s+(c|bc)\b|exx\b|in\s+c\s*,)"
)


@dataclass(frozen=True, slots=True)
class _Ports:
    known: Mapping[int, str]
    unknown: str | None

    def kind(self, port: int | None) -> str | None:
        if port is None:
            return self.unknown
        return self.known.get(port & PORT_MASK)


def parse(text: str, *, ports: Mapping[int, str], unknown_port: str | None) -> Listing:
    named = _Ports(known=ports, unknown=unknown_port)
    instructions: list[Instruction] = []
    owners: list[str | None] = []
    labels: dict[str, int] = {}
    owner: str | None = None
    port_register: int | None = None
    entered = _entered(text)
    for line in text.splitlines():
        label = LABEL.match(line)
        if label:
            name = label.group(2).rstrip(GLOBAL_MARK)
            owner = name if label.group(2).endswith(GLOBAL_MARK) or name in entered else owner
            labels = {**labels, _scoped(name, owner): int(label.group(1), 16)}
            port_register = port_register if name.endswith(LOCAL_SUFFIX) else None
            continue
        read = _instruction(line, port_register, named)
        if read is not None:
            instruction, port_register = read
            instructions = [*instructions, instruction]
            owners = [*owners, owner]
    resolved = [
        replace(instruction, target=_target(instruction.text, labels, owner))
        for instruction, owner in zip(instructions, owners, strict=True)
    ]
    return Listing(instructions=resolved, labels=labels, owners=owners)


def _entered(text: str) -> set[str]:
    bodies = [code.group(4) for code in map(CODE.match, text.splitlines()) if code]
    called = {call.group(2) for call in map(CALL.match, bodies) if call}
    jumped = {jump.group(3) for jump in map(BRANCH.match, bodies) if jump}
    return {name for name in called | jumped if name.startswith(FUNCTION_PREFIX)}


def _instruction(
    line: str, port_register: int | None, ports: _Ports
) -> tuple[Instruction, int | None] | None:
    code = CODE.match(line)
    body = code.group(4) if code else ""
    if code is None or not body or body.startswith(";"):
        return None
    register = _port_register_after(body, port_register)
    cycles = int(code.group(3))
    port = _port_of(body, register, ports)
    conditional = _conditional(body)
    instruction = Instruction(
        address=int(code.group(1), 16),
        cycles=cycles,
        text=body,
        port=port,
        fall_cycles=_not_taken(body, cycles, conditional=conditional),
        conditional=conditional,
        leaves=_leaves(body, conditional=conditional),
        returns=body.split()[0].lower() == "ret",
        call=_called(body),
        jumped=_jumped(body),
        repeats=REPEAT_INTERVAL if port is not None and REPEATING_OUTPUT.match(body) else None,
    )
    return instruction, register


def _scoped(name: str, owner: str | None) -> str:
    return f"{owner}/{name}" if name.endswith(LOCAL_SUFFIX) and owner else name


def _port_register_after(body: str, port_register: int | None) -> int | None:
    loaded = LOAD_C.match(body)
    if loaded:
        return int(loaded.group(1), 0)
    if CLOBBER_C.match(body):
        return None
    return port_register


def _port_of(body: str, port_register: int | None, ports: _Ports) -> str | None:
    immediate = PORT_IMMEDIATE.match(body)
    if immediate:
        return ports.known.get(int(immediate.group(1), 0) & PORT_MASK)
    if BLOCK_OUTPUT.match(body) or PORT_REGISTER.match(body):
        return ports.kind(port_register)
    return None


def _conditional(body: str) -> bool:
    mnemonic = body.split(maxsplit=1)[0].lower()
    operands = body[len(mnemonic) :].strip()
    if mnemonic == "djnz":
        return True
    if mnemonic in {"jr", "jp", "call"}:
        return "," in operands
    return mnemonic == "ret" and bool(operands)


def _not_taken(body: str, cycles: int, *, conditional: bool) -> int:
    if not conditional:
        return cycles
    return NOT_TAKEN_CYCLES.get(body.split(maxsplit=1)[0].lower(), cycles)


def _leaves(body: str, *, conditional: bool) -> bool:
    if UNCONDITIONAL_END.match(body):
        return not conditional
    branch = BRANCH.match(body)
    return bool(branch and branch.group(1) in {"jp", "jr"} and branch.group(2) is None)


def _called(body: str) -> str | None:
    call = CALL.match(body)
    return call.group(2) if call else None


def _jumped(body: str) -> str | None:
    branch = BRANCH.match(body)
    name = branch.group(3).strip() if branch else ""
    return name if name.startswith(FUNCTION_PREFIX) else None


def _target(body: str, labels: dict[str, int], owner: str | None) -> int | None:
    branch = BRANCH.match(body)
    if branch is None:
        return None
    name = branch.group(3).strip()
    return labels.get(_scoped(name, owner), labels.get(name))
