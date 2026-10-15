from __future__ import annotations

import heapq
from dataclasses import dataclass, field

Node = tuple[str, int]
Edge = tuple[Node, int, bool]


@dataclass(frozen=True, slots=True)
class Instruction:
    address: int
    cycles: int
    text: str
    port: str | None
    fall_cycles: int
    conditional: bool
    leaves: bool
    returns: bool
    call: str | None = None
    jumped: str | None = None
    repeats: int | None = None
    target: int | None = None

    @property
    def mnemonic(self) -> str:
        return self.text.split()[0] if self.text else ""


@dataclass(frozen=True, slots=True)
class Listing:
    instructions: list[Instruction]
    labels: dict[str, int]
    owners: list[str | None] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Gap:
    source: str
    first: Instruction
    second: Instruction
    cycles: int
    wrapped: bool
    to_source: str = ""
    unit: str = "cycles"

    def describe(self) -> str:
        route = "around the loop" if self.wrapped else "falling through"
        landing = (
            f" in {self.to_source}" if self.to_source and self.to_source != self.source else ""
        )
        return (
            f"{self.source}: {self.cycles} {self.unit} from {self.first.port} write at "
            f"0x{self.first.address:04X} to {self.second.port} write at "
            f"0x{self.second.address:04X}{landing}, {route}"
        )


@dataclass(frozen=True, slots=True)
class Program:
    listings: dict[str, Listing]
    unit: str = "cycles"

    def at(self, node: Node) -> Instruction:
        source, index = node
        return self.listings[source].instructions[index]

    def entry(self, name: str) -> Node | None:
        for source, listing in self.listings.items():
            address = listing.labels.get(name)
            if address is None:
                continue
            for index, instruction in enumerate(listing.instructions):
                if instruction.address >= address:
                    return (source, index)
        return None

    def return_sites(self, function: str | None) -> list[Node]:
        owners = self._tail_callers(function)
        return [
            (source, index + 1)
            for source, listing in self.listings.items()
            for index, instruction in enumerate(listing.instructions)
            if instruction.call in owners and index + 1 < len(listing.instructions)
        ]

    def size(self) -> int:
        return sum(len(listing.instructions) for listing in self.listings.values())

    def _tail_callers(self, function: str | None) -> set[str]:
        found: set[str] = set()
        pending = [function] if function else []
        for _ in range(self.size() + 2):
            if not pending:
                return found
            name = pending.pop()
            if name in found:
                continue
            found = {*found, name}
            pending = [*pending, *self._jumping_to(name)]
        msg = f"tail calls into {function} do not settle"
        raise ValueError(msg)

    def _jumping_to(self, name: str) -> list[str]:
        return [
            owner
            for listing in self.listings.values()
            for instruction, owner in zip(listing.instructions, listing.owners, strict=True)
            if owner is not None and instruction.jumped == name
        ]


def gaps(program: Program, *, budget: int | None = None) -> list[Gap]:
    limit = walk_budget(program) if budget is None else budget
    return _repeating(program) + _cheapest_paths(program, limit)


def walk_budget(program: Program) -> int:
    nodes = [
        (source, index)
        for source, listing in program.listings.items()
        for index in range(len(listing.instructions))
    ]
    return sum(len(_edges(program, node)) for node in nodes) + 1


def _repeating(program: Program) -> list[Gap]:
    return [
        Gap(source, instruction, instruction, instruction.repeats, True, unit=program.unit)
        for source, listing in program.listings.items()
        for instruction in listing.instructions
        if instruction.repeats is not None
    ]


def _cheapest_paths(program: Program, budget: int) -> list[Gap]:
    starts = [
        (source, index)
        for source, listing in program.listings.items()
        for index, first in enumerate(listing.instructions)
        if first.port is not None
    ]
    return [gap for start in starts for gap in _paths_from(program, start, budget)]


def _paths_from(program: Program, start: Node, budget: int) -> list[Gap]:
    first = program.at(start)
    reached: dict[Node, tuple[int, bool]] = {}
    best: dict[Node, int] = {}
    pending = [(cost, back, node) for node, cost, back in _edges(program, start)]
    heapq.heapify(pending)
    for _ in range(budget):
        if not pending:
            break
        cycles, wrapped, node = heapq.heappop(pending)
        if best.get(node, cycles + 1) <= cycles:
            continue
        best[node] = cycles
        if program.at(node).port is not None:
            reached[node] = (cycles, wrapped)
            continue
        for after, cost, back in _edges(program, node):
            heapq.heappush(pending, (cycles + cost, wrapped or back, after))
    else:
        msg = f"the walk from 0x{first.address:04X} in {start[0]} did not settle"
        raise ValueError(msg)
    return [
        Gap(start[0], first, program.at(node), cycles, wrapped, node[0], program.unit)
        for node, (cycles, wrapped) in sorted(reached.items())
    ]


def _edges(program: Program, node: Node) -> list[Edge]:
    source, index = node
    listing = program.listings[source]
    current = listing.instructions[index]
    owner = listing.owners[index] if index < len(listing.owners) else None
    entry = program.entry(current.call) if current.call else None
    edges: list[Edge] = [(entry, current.cycles, False)] if entry is not None else []
    falls = index + 1 < len(listing.instructions) and not current.leaves
    if falls and (entry is None or current.conditional):
        edges = [*edges, ((source, index + 1), current.fall_cycles, False)]
    if current.returns:
        edges = [*edges, *_returns(program, owner, current.cycles)]
    return [*edges, *_branches(program, source, current, owner)]


def _branches(program: Program, source: str, current: Instruction, owner: str | None) -> list[Edge]:
    listing = program.listings[source]
    if current.target is not None:
        landing = _index_at(listing, current.target)
        if landing is None:
            return []
        return [((source, landing), current.cycles, current.target <= current.address)]
    elsewhere = program.entry(current.jumped) if current.jumped else None
    if elsewhere is not None:
        return [(elsewhere, current.cycles, False)]
    if current.jumped:
        return _returns(program, owner, current.cycles)
    return []


def _returns(program: Program, owner: str | None, cycles: int) -> list[Edge]:
    return [(site, cycles, True) for site in program.return_sites(owner)]


def _index_at(listing: Listing, address: int) -> int | None:
    for index, instruction in enumerate(listing.instructions):
        if instruction.address >= address:
            return index
    return None
