from __future__ import annotations

import textwrap

from fmvcore import sdccz80

DATA = "data"
CONTROL = "control"
PORTS = {0xBE: DATA, 0xBF: CONTROL}

UNROLLED_LOOP = """
    00000038 0E BE            [ 7]  103 \tld\tc, #0xBE
    0000003A ED A3            [16]  105 \touti
    0000003C ED A3            [16]  106 \touti
    00000040 C9               [10]  108 \tret
"""

PACED_LOOP = """
    00000038 0E BE            [ 7]  103 \tld\tc, #0xBE
    0000003A                        104 00050$:
    0000003A ED A3            [16]  105 \touti
    0000003C 00               [ 4]  106 \tnop
    0000003D C2r3Ar00         [10]  107 \tjp\tnz, 00050$
    00000040 C9               [10]  108 \tret
"""

CLOBBERED_PORT_REGISTER = """
    00000010 0E BF            [ 7]    1 \tld\tc, #0xBF
    00000012 4F               [ 4]    2 \tld\tc, a
    00000013 ED A3            [16]    3 \touti
    00000015 C9               [10]    5 \tret
"""

PORT_REGISTER_ACROSS_FUNCTIONS = """
    00000010 0E BF            [ 7]    1 \tld\tc, #0xBF
    00000012 C9               [10]    2 \tret
    00000013                          3 _next:
    00000013 ED A3            [16]    4 \touti
    00000015 C9               [10]    6 \tret
"""

TWO_FUNCTIONS_ONE_LOCAL_LABEL = """
    00000000                          7 _first::
    00000000                          8 00104$:
    00000000 00               [ 4]    9 \tnop
    00000001 C9               [10]   10 \tret
    00000002                         11 _second::
    00000002 D3 BE            [11]   12 \tout\t(#0xBE), a
    00000004                         13 00104$:
    00000004 18 FC            [12]   14 \tjr\t00104$
"""

DATA_LABEL_INSIDE_A_FUNCTION = """
    00000000                          7 _set_register::
    00000000 D3 BF            [11]    8 \tout\t(#0xBF), a
    00000002 18 03            [12]    9 \tjr\t00102$
    00000004                         10 __str_0:
    00000004 41 42 00                11 \t.ascii "AB"
    00000007                         12 00102$:
    00000007 C9               [10]   13 \tret
    00000008                         14 _caller::
    00000008 CDr00r00         [17]   15 \tcall\t_set_register
    0000000B D3 BF            [11]   16 \tout\t(#0xBF), a
    0000000D C9               [10]   17 \tret
"""


def read(text: str) -> sdccz80.Listing:
    return sdccz80.parse(textwrap.dedent(text), ports=PORTS, unknown_port=DATA)


class TestReadingInstructions:
    def test_cycles_and_mnemonics_come_from_the_assembler(self):
        # Arrange
        text = PACED_LOOP

        # Act
        listing = read(text)

        # Assert
        assert [(i.mnemonic, i.cycles) for i in listing.instructions] == [
            ("ld", 7),
            ("outi", 16),
            ("nop", 4),
            ("jp", 10),
            ("ret", 10),
        ]

    def test_a_label_records_its_address(self):
        # Arrange
        text = PACED_LOOP

        # Act
        listing = read(text)

        # Assert
        assert listing.labels["00050$"] == 0x3A

    def test_an_empty_listing_reads_as_nothing(self):
        # Arrange
        text = ""

        # Act
        listing = read(text)

        # Assert
        assert (listing.instructions, listing.labels) == ([], {})


class TestPorts:
    def test_an_immediate_write_takes_the_named_port(self):
        # Arrange
        text = "    00000010 D3 BF            [11]   1 \tout\t(#0xBF), a\n"

        # Act
        listing = read(text)

        # Assert
        assert listing.instructions[0].port == CONTROL

    def test_a_block_output_follows_the_port_register(self):
        # Arrange
        text = UNROLLED_LOOP

        # Act
        listing = read(text)

        # Assert
        assert [i.port for i in listing.instructions] == [None, DATA, DATA, None]

    def test_a_port_the_map_does_not_name_is_no_write(self):
        # Arrange
        text = "    00000010 D3 7F            [11]   1 \tout\t(#0x7F), a\n"

        # Act
        listing = read(text)

        # Assert
        assert listing.instructions[0].port is None

    def test_overwriting_c_falls_back_to_the_unknown_port(self):
        # Arrange
        text = CLOBBERED_PORT_REGISTER

        # Act
        listing = read(text)

        # Assert
        assert listing.instructions[2].port == DATA

    def test_a_new_function_forgets_the_port_register(self):
        # Arrange
        text = PORT_REGISTER_ACROSS_FUNCTIONS

        # Act
        listing = read(text)

        # Assert
        assert listing.instructions[2].port == DATA


class TestBranches:
    def test_a_conditional_jump_costs_its_listed_cycles_taken_and_the_same_untaken(self):
        # Arrange
        text = PACED_LOOP

        # Act
        jump = read(text).instructions[3]

        # Assert
        assert (jump.conditional, jump.cycles, jump.fall_cycles, jump.target) == (
            True,
            10,
            10,
            0x3A,
        )

    def test_a_relative_jump_not_taken_costs_seven(self):
        # Arrange
        text = "    00000012 28 04            [12]    2 \tjr\tz, 00090$\n"

        # Act
        jump = read(text).instructions[0]

        # Assert
        assert (jump.cycles, jump.fall_cycles) == (12, 7)

    def test_an_uppercase_condition_is_a_condition(self):
        # Arrange
        text = "    00000002 20 FC            [12]   10 \tjr\tNZ, 00101$\n"

        # Act
        jump = read(text).instructions[0]

        # Assert
        assert (jump.conditional, jump.leaves) == (True, False)

    def test_an_unconditional_return_leaves_and_a_conditional_one_falls_through(self):
        # Arrange
        text = (
            "    00000012 C0               [11]    2 \tret\tNZ\n"
            "    00000015 C9               [10]    4 \tret\n"
        )

        # Act
        first, second = read(text).instructions

        # Assert
        assert [(i.returns, i.leaves, i.fall_cycles) for i in (first, second)] == [
            (True, False, 5),
            (True, True, 10),
        ]

    def test_a_call_and_a_tail_jump_name_their_functions(self):
        # Arrange
        text = (
            "    00000000 CDr00r00         [17]    8 \tcall\t_set_register\n"
            "    00000003 C3r00r00         [10]   13 \tjp\t_SMS_somewhere\n"
        )

        # Act
        call, jump = read(text).instructions

        # Assert
        assert (call.call, jump.jumped, jump.target, jump.leaves) == (
            "_set_register",
            "_SMS_somewhere",
            None,
            True,
        )

    def test_a_repeating_output_carries_its_own_interval(self):
        # Arrange
        text = (
            "    00000038 0E BE            [ 7]  103 \tld\tc, #0xBE\n"
            "    0000003A ED B3            [21]  104 \totir\n"
        )

        # Act
        otir = read(text).instructions[1]

        # Assert
        assert (otir.port, otir.repeats) == (DATA, sdccz80.REPEAT_INTERVAL)


class TestOwnership:
    def test_a_local_label_resolves_inside_its_own_function(self):
        # Arrange
        text = TWO_FUNCTIONS_ONE_LOCAL_LABEL

        # Act
        listing = read(text)

        # Assert
        assert (listing.labels["_first/00104$"], listing.labels["_second/00104$"]) == (0, 4)
        assert listing.instructions[-1].target == 4

    def test_a_data_label_inside_a_function_owns_no_code(self):
        # Arrange
        text = DATA_LABEL_INSIDE_A_FUNCTION

        # Act
        listing = read(text)

        # Assert
        assert listing.owners == ["_set_register"] * 3 + ["_caller"] * 3
