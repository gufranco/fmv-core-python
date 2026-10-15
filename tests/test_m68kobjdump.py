from __future__ import annotations

import pytest

from fmvcore import m68kobjdump

ADDRESS = "address"
DATA = "data"
MODULO = "modulo"
PORTS = {0x3C0000: ADDRESS, 0x3C0002: DATA, 0x3C0004: MODULO}


def listing(name: str, *rows: str, section: str = ".text") -> str:
    header = [f"{name}:     file format elf32-m68k", "", "", f"Disassembly of section {section}:"]
    return "\n".join(header + list(rows)) + "\n"


def symbol(address: int, name: str) -> str:
    return f"\n{address:08x} <{name}>:"


def op(address: int, encoding: str, text: str) -> str:
    return f"{address:4x}:\t{encoding:<15}\t{text}"


def tail(address: int, encoding: str) -> str:
    return f"{address:4x}:\t{encoding} "


def reloc(address: int, name: str) -> str:
    return f"\t\t\t{address:x}: R_68K_32\t{name}"


def crossing(spacings: list[m68kobjdump.Spacing]) -> list[tuple[int, int, str, str, int]]:
    return [
        (s.first.address, s.second.address, s.leaving.kind or "", s.arriving.kind or "", s.cycles)
        for s in spacings
        if s.first is not s.second
    ]


class TestOneObject:
    def test_a_long_immediate_write_then_a_register_write_is_twelve_cycles_apart(self):
        # Arrange
        text = listing(
            "a.o",
            symbol(0x4D6, "sample"),
            op(0x4D6, "23fc 74ba 1016", "movel #1958350870,3c0000 <sample+0x3bfb2a>"),
            tail(0x4DC, "003c 0000"),
            op(0x4E0, "23c9 003c 0000", "movel %a1,3c0000 <sample+0x3bfb2a>"),
            op(0x4E6, "4e75", "rts"),
        )
        reading = m68kobjdump.read({"a.o": text}, ports=PORTS)

        # Act
        spacings = m68kobjdump.spacings(reading)

        # Assert
        assert crossing(spacings) == [(0x4D6, 0x4E0, DATA, ADDRESS, 12)]

    def test_the_halves_of_one_long_write_are_spaced_by_their_bus_cycles(self):
        # Arrange
        text = listing(
            "a.o",
            symbol(0x100, "sample"),
            op(0x100, "23c1 003c 0002", "movel %d1,3c0002 <sample+0x3bff02>"),
            op(0x106, "4e75", "rts"),
        )
        reading = m68kobjdump.read({"a.o": text}, ports=PORTS)

        # Act
        spacings = m68kobjdump.spacings(reading)

        # Assert
        assert [(s.leaving.kind, s.arriving.kind, s.cycles) for s in spacings] == [
            (DATA, MODULO, 0)
        ]

    def test_a_backward_branch_reaches_the_same_write_again(self):
        # Arrange
        text = listing(
            "a.o",
            symbol(0x100, "sample"),
            op(0x100, "207c 003c 0000", "moveal #3932160,%a0"),
            op(0x106, "2080", "movel %d0,%a0@"),
            op(0x108, "60fc", "bras 106 <sample+0x6>"),
        )
        reading = m68kobjdump.read({"a.o": text}, ports=PORTS)

        # Act
        spacings = m68kobjdump.spacings(reading)

        # Assert
        assert [(s.leaving.kind, s.arriving.kind, s.cycles) for s in spacings] == [
            (ADDRESS, DATA, 0),
            (DATA, ADDRESS, 14),
        ]

    def test_a_clobbered_address_register_no_longer_points_at_a_port(self):
        # Arrange
        text = listing(
            "a.o",
            symbol(0x100, "sample"),
            op(0x100, "207c 003c 0000", "moveal #3932160,%a0"),
            op(0x106, "2049", "moveal %a1,%a0"),
            op(0x108, "3080", "movew %d0,%a0@"),
            op(0x10A, "4e75", "rts"),
        )
        reading = m68kobjdump.read({"a.o": text}, ports=PORTS)

        # Act
        spacings = m68kobjdump.spacings(reading)

        # Assert
        assert spacings == []

    def test_a_movem_forgets_every_held_port(self):
        # Arrange
        text = listing(
            "a.o",
            symbol(0x100, "sample"),
            op(0x100, "207c 003c 0002", "moveal #3932162,%a0"),
            op(0x106, "4cdf 0300", "moveml %sp@+,%a0-%a1"),
            op(0x10A, "3080", "movew %d0,%a0@"),
            op(0x10C, "4e75", "rts"),
        )
        reading = m68kobjdump.read({"a.o": text}, ports=PORTS)

        # Act
        spacings = m68kobjdump.spacings(reading)

        # Assert
        assert spacings == []


class TestCalls:
    def test_a_write_inside_a_callee_in_another_object_is_reached(self):
        # Arrange
        caller = listing(
            "a.o",
            symbol(0x0, "main"),
            op(0x0, "33fc 0000 003c", "movew #0,3c0002 <main+0x3c0002>"),
            tail(0x6, "0002"),
            op(0x8, "4eb9 0000 0000", "jsr 0 <main>"),
            reloc(0xA, "helper"),
            op(0xE, "4e75", "rts"),
        )
        callee = listing(
            "b.o",
            symbol(0x0, "helper"),
            op(0x0, "33fc 0001 003c", "movew #1,3c0002 <helper+0x3c0002>"),
            tail(0x6, "0002"),
            op(0x8, "4e75", "rts"),
        )
        reading = m68kobjdump.read({"a.o": caller, "b.o": callee}, ports=PORTS)

        # Act
        spacings = m68kobjdump.spacings(reading)

        # Assert
        assert [(s.source, s.to_source, s.cycles) for s in spacings] == [
            ("a.o:.text", "b.o:.text", 34)
        ]

    def test_a_write_after_the_call_site_is_reached_across_rts(self):
        # Arrange
        text = listing(
            "a.o",
            symbol(0x0, "poke"),
            op(0x0, "33fc 0000 003c", "movew #0,3c0002 <poke+0x3c0002>"),
            tail(0x6, "0002"),
            op(0x8, "4e75", "rts"),
            symbol(0xA, "main"),
            op(0xA, "4eb9 0000 0000", "jsr 0 <poke>"),
            reloc(0xC, "poke"),
            op(0x10, "33fc 8000 003c", "movew #-32768,3c0000 <poke+0x3c0000>"),
            tail(0x16, "0000"),
            op(0x18, "4e75", "rts"),
        )
        reading = m68kobjdump.read({"a.o": text}, ports=PORTS)

        # Act
        spacings = m68kobjdump.spacings(reading)

        # Assert
        assert crossing(spacings) == [(0x0, 0x10, DATA, ADDRESS, 32)]

    def test_an_indirect_call_costs_its_cycles_and_falls_through(self):
        # Arrange
        text = listing(
            "a.o",
            symbol(0x0, "main"),
            op(0x0, "33fc 0000 003c", "movew #0,3c0002 <main+0x3c0002>"),
            tail(0x6, "0002"),
            op(0x8, "4e93", "jsr %a3@"),
            op(0xA, "33fc 0001 003c", "movew #1,3c0002 <main+0x3c0002>"),
            tail(0x10, "0002"),
            op(0x12, "4e75", "rts"),
        )
        reading = m68kobjdump.read({"a.o": text}, ports=PORTS)

        # Act
        spacings = m68kobjdump.spacings(reading)

        # Assert
        assert crossing(spacings) == [(0x0, 0xA, DATA, DATA, 34)]

    def test_a_tail_jump_into_another_function_reaches_its_write(self):
        # Arrange
        text = listing(
            "a.o",
            symbol(0x0, "main"),
            op(0x0, "33fc 0000 003c", "movew #0,3c0002 <main+0x3c0002>"),
            tail(0x6, "0002"),
            op(0x8, "4ef9 0000 0000", "jmp 0 <main>"),
            reloc(0xA, "helper"),
            symbol(0xE, "helper"),
            op(0xE, "33fc 0001 003c", "movew #1,3c0002 <main+0x3c0002>"),
            tail(0x14, "0002"),
            op(0x16, "4e75", "rts"),
        )
        reading = m68kobjdump.read({"a.o": text}, ports=PORTS)

        # Act
        spacings = m68kobjdump.spacings(reading)

        # Assert
        assert crossing(spacings) == [(0x0, 0xE, DATA, DATA, 26)]


class TestRefusals:
    def test_a_call_through_a_section_symbol_with_no_function_there_is_refused(self):
        # Arrange
        text = listing(
            "a.o",
            symbol(0x0, "main"),
            op(0x0, "4eb9 0000 0000", "jsr 0 <main>"),
            reloc(0x2, ".text+0x40"),
            op(0x6, "4e75", "rts"),
        )

        # Act
        with pytest.raises(m68kobjdump.UnresolvedCallError) as refused:
            m68kobjdump.read({"a.o": text}, ports=PORTS)

        # Assert
        assert str(refused.value) == "a.o:.text 0x0000: no function at .text+0x40"

    def test_an_unmodelled_write_form_is_refused(self):
        # Arrange
        text = listing(
            "a.o",
            symbol(0x100, "main"),
            op(0x100, "33f0 0800 003c", "movew %a0@(0,%d0:l),3c0002 <main+0x3bff02>"),
            tail(0x106, "0002"),
            op(0x108, "4e75", "rts"),
        )

        # Act
        with pytest.raises(m68kobjdump.UnmodelledWriteError) as refused:
            m68kobjdump.read({"a.o": text}, ports=PORTS)

        # Assert
        assert str(refused.value) == "word absolute write from '%a0@(0,%d0:l)'"


class TestCycles:
    @pytest.mark.parametrize(
        ("mnemonic", "cycles"),
        [("moveq", 4), ("rts", 16), ("bras", 10), ("dbf", 10), ("bnes", 8), ("btst", 4)],
    )
    def test_each_mnemonic_costs_its_tabled_cycles(self, mnemonic, cycles):
        # Arrange
        name = mnemonic

        # Act
        cost = m68kobjdump.cycles_for(name)

        # Assert
        assert cost == cycles


class TestIndirectWrites:
    @pytest.mark.parametrize(
        ("text", "cycles", "offsets"),
        [
            ("movew %d0,%a0@", 8, (4,)),
            ("movew %a1@,%a0@", 12, (8,)),
            ("movew %a1@(-2),%a0@", 16, (12,)),
            ("movel %d0,%a0@", 12, (4, 8)),
        ],
    )
    def test_each_modelled_form_has_its_cycles_and_bus_offsets(self, text, cycles, offsets):
        # Arrange
        source = listing(
            "a.o",
            symbol(0x100, "main"),
            op(0x100, "207c 003c 0000", "moveal #3932160,%a0"),
            op(0x106, "3080", text),
            op(0x108, "4e75", "rts"),
        )

        # Act
        reading = m68kobjdump.read({"a.o": source}, ports=PORTS)

        # Assert
        written = reading.program.listings["a.o:.text"].instructions[1]
        found = reading.accesses[("a.o:.text", 0x106)]
        assert (written.cycles, tuple(a.offset for a in found)) == (cycles, offsets)

    def test_an_unmodelled_indirect_form_is_refused(self):
        # Arrange
        source = listing(
            "a.o",
            symbol(0x100, "main"),
            op(0x100, "207c 003c 0000", "moveal #3932160,%a0"),
            op(0x106, "2091", "movel %a1@,%a0@"),
            op(0x108, "4e75", "rts"),
        )

        # Act
        with pytest.raises(m68kobjdump.UnmodelledWriteError) as refused:
            m68kobjdump.read({"a.o": source}, ports=PORTS)

        # Assert
        assert str(refused.value) == "long register indirect write from '%a1@'"


class TestDataRelocations:
    def test_a_relocation_on_an_instruction_that_does_not_branch_is_ignored(self):
        # Arrange
        text = listing(
            "a.o",
            symbol(0x0, "main"),
            op(0x0, "4879 0000 0000", "pea 0 <main>"),
            reloc(0x2, ".bss"),
            op(0x6, "4e75", "rts"),
        )

        # Act
        reading = m68kobjdump.read({"a.o": text}, ports=PORTS)

        # Assert
        pushed = reading.program.listings["a.o:.text"].instructions[0]
        assert (pushed.call, pushed.jumped, pushed.target) == (None, None, None)


class TestSectionRelativeCalls:
    def test_a_static_function_in_another_section_is_called_and_returns(self):
        # Arrange
        text = "\n".join(
            [
                listing(
                    "a.o",
                    symbol(0x0, "poke"),
                    op(0x0, "33fc 0000 003c", "movew #0,3c0002 <poke+0x3c0002>"),
                    tail(0x6, "0002"),
                    op(0x8, "4e75", "rts"),
                ).rstrip("\n"),
                "",
                "Disassembly of section .text.startup:",
                symbol(0x0, "main"),
                op(0x0, "4eb9 0000 0000", "jsr 0 <main>"),
                reloc(0x2, ".text"),
                op(0x6, "33fc 8000 003c", "movew #-32768,3c0000 <main+0x3c0000>"),
                tail(0xC, "0000"),
                op(0xE, "4e75", "rts"),
            ]
        )
        reading = m68kobjdump.read({"a.o": text}, ports=PORTS)

        # Act
        spacings = m68kobjdump.spacings(reading)

        # Assert
        assert [(s.source, s.to_source, s.cycles) for s in spacings] == [
            ("a.o:.text", "a.o:.text.startup", 32)
        ]

    def test_a_section_symbol_with_an_offset_names_the_function_at_it(self):
        # Arrange
        text = "\n".join(
            [
                listing(
                    "a.o",
                    symbol(0x0, "first"),
                    op(0x0, "4e75", "rts"),
                    symbol(0x2, "second"),
                    op(0x2, "4e75", "rts"),
                ).rstrip("\n"),
                "",
                "Disassembly of section .text.startup:",
                symbol(0x0, "main"),
                op(0x0, "4eb9 0000 0000", "jsr 0 <main>"),
                reloc(0x2, ".text+0x2"),
                op(0x6, "4e75", "rts"),
            ]
        )

        # Act
        reading = m68kobjdump.read({"a.o": text}, ports=PORTS)

        # Assert
        assert reading.program.listings["a.o:.text.startup"].instructions[0].call == "second"
