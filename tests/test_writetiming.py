from __future__ import annotations

import textwrap

import pytest

from fmvcore import sdccz80, writetiming

PORTS = {0xBE: "data", 0xBF: "control"}

NOT_TAKEN_PATH = """
    00000010 D3 BE            [11]    1 \tout\t(#0xBE), a
    00000012 28 04            [12]    2 \tjr\tz, 00090$
    00000014 D3 BE            [11]    3 \tout\t(#0xBE), a
    00000016 C9               [10]    4 \tret
    00000018                          5 00090$:
    00000018 C9               [10]    6 \tret
"""

FORWARD_TAKEN = """
    00000010 D3 BE            [11]    1 \tout\t(#0xBE), a
    00000012 28 05            [12]    2 \tjr\tz, 00090$
    00000014 00               [ 4]    3 \tnop
    00000015 00               [ 4]    4 \tnop
    00000016 00               [ 4]    5 \tnop
    00000017 00               [ 4]    6 \tnop
    00000018 00               [ 4]    7 \tnop
    00000019                          8 00090$:
    00000019 D3 BE            [11]    9 \tout\t(#0xBE), a
    0000001B C9               [10]   10 \tret
"""

CONDITIONAL_RETURN = """
    00000010 D3 BE            [11]    1 \tout\t(#0xBE), a
    00000012 C0               [11]    2 \tret\tNZ
    00000013 D3 BE            [11]    3 \tout\t(#0xBE), a
    00000015 C9               [10]    4 \tret
"""

PACED_LOOP = """
    00000038 0E BE            [ 7]  103 \tld\tc, #0xBE
    0000003A                        104 00050$:
    0000003A ED A3            [16]  105 \touti
    0000003C 00               [ 4]  106 \tnop
    0000003D C2r3Ar00         [10]  107 \tjp\tnz, 00050$
    00000040 C9               [10]  108 \tret
"""

REPEATING = """
    00000038 0E BE            [ 7]  103 \tld\tc, #0xBE
    0000003A ED B3            [21]  104 \totir
    0000003C C9               [10]  105 \tret
"""

UPPERCASE_CONDITION_LOOP = """
    00000000                          7 _spin::
    00000000                          8 00101$:
    00000000 D3 BE            [11]    9 \tout\t(#0xBE), a
    00000002 20 FC            [12]   10 \tjr\tNZ, 00101$
    00000004 C9               [10]   11 \tret
"""

CALLEE_ENDING_ON_A_WRITE = """
    00000000                          7 _set_register::
    00000000 D3 BF            [11]    8 \tout\t(#0xBF), a
    00000002 C9               [10]    9 \tret
"""

CALLER_WRITING_AT_ONCE = """
    00000000                          7 _caller::
    00000000 CDr00r00         [17]    8 \tcall\t_set_register
    00000003 D3 BF            [11]    9 \tout\t(#0xBF), a
    00000005 C9               [10]   10 \tret
"""

CALLER_WRITING_THEN_CALLING = """
    00000000                          7 _caller::
    00000000 D3 BF            [11]    8 \tout\t(#0xBF), a
    00000002 CDr00r00         [17]    9 \tcall\t_set_register
    00000005 C9               [10]   10 \tret
"""

TAIL_JUMP_INTO_A_LISTED_FUNCTION = """
    00000000                          7 _caller::
    00000000 D3 BF            [11]    8 \tout\t(#0xBF), a
    00000002 C3r00r00         [10]    9 \tjp\t_set_register
"""

TAIL_JUMP_OUT_OF_THE_LISTINGS = """
    00000000                          7 _caller::
    00000000 CDr00r00         [17]    8 \tcall\t_finish
    00000003 D3 BF            [11]    9 \tout\t(#0xBF), a
    00000005 C9               [10]   10 \tret
    00000006                         11 _finish::
    00000006 D3 BF            [11]   12 \tout\t(#0xBF), a
    00000008 C3r00r00         [10]   13 \tjp\t_SMS_somewhere
"""

TAIL_JUMPS_IN_A_CIRCLE = """
    00000000                          7 _ping::
    00000000 C3r00r00         [10]    8 \tjp\t_pong
    00000003                          9 _pong::
    00000003 C8               [11]   10 \tret\tz
    00000004 C3r00r00         [10]   11 \tjp\t_ping
    00000006                         11 _start::
    00000006 D3 BF            [11]   12 \tout\t(#0xBF), a
    00000008 CDr00r00         [17]   13 \tcall\t_ping
    0000000B D3 BF            [11]   14 \tout\t(#0xBF), a
    0000000D C9               [10]   15 \tret
"""

BRANCH_TO_THE_END = """
    00000000                          7 _leave::
    00000000 D3 BF            [11]    8 \tout\t(#0xBF), a
    00000002 18 00            [12]    9 \tjr\t00199$
    00000004                         10 00199$:
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


def program(**texts: str) -> writetiming.Program:
    return writetiming.Program(
        listings={
            name: sdccz80.parse(textwrap.dedent(text), ports=PORTS, unknown_port="data")
            for name, text in texts.items()
        },
        unit=sdccz80.CYCLE_UNIT,
    )


def branching(branches: int) -> str:
    lines = ["    00000010 D3 BE            [11]    1 \tout\t(#0xBE), a"]
    for step in range(branches):
        address = 0x12 + step * 2
        lines.append(f"    {address:08X} 28 00            [12]    2 \tjr\tz, 0{step:04d}$")
        lines.append(f"    {address + 2:08X}                          3 0{step:04d}$:")
    end = 0x12 + branches * 2
    lines.append(f"    {end:08X} D3 BE            [11]    4 \tout\t(#0xBE), a")
    return "\n".join(lines) + "\n"


def cycles(found: list[writetiming.Gap]) -> list[int]:
    return [gap.cycles for gap in found]


class TestPathsInsideOneListing:
    def test_a_loop_is_measured_around_its_branch(self):
        # Arrange
        loop = program(paced=PACED_LOOP)

        # Act
        found = writetiming.gaps(loop)

        # Assert
        assert [(gap.cycles, gap.wrapped) for gap in found] == [(30, True)]

    def test_a_branch_not_taken_costs_its_short_figure(self):
        # Arrange
        listing = program(fall=NOT_TAKEN_PATH)

        # Act
        found = writetiming.gaps(listing)

        # Assert
        assert cycles(found) == [18]

    def test_a_forward_branch_taken_reaches_a_write_the_straight_walk_would_miss(self):
        # Arrange
        listing = program(taken=FORWARD_TAKEN)

        # Act
        found = writetiming.gaps(listing)

        # Assert
        assert cycles(found) == [23]

    def test_a_conditional_return_does_not_end_the_path(self):
        # Arrange
        listing = program(ret=CONDITIONAL_RETURN)

        # Act
        found = writetiming.gaps(listing)

        # Assert
        assert cycles(found) == [16]

    def test_a_repeating_output_paces_itself(self):
        # Arrange
        listing = program(repeating=REPEATING)

        # Act
        found = writetiming.gaps(listing)

        # Assert
        assert cycles(found) == [sdccz80.REPEAT_INTERVAL]

    def test_an_uppercase_condition_closes_its_loop(self):
        # Arrange
        listing = program(spin=UPPERCASE_CONDITION_LOOP)

        # Act
        found = writetiming.gaps(listing)

        # Assert
        assert [(gap.cycles, gap.wrapped) for gap in found] == [(23, True)]

    def test_a_branch_to_a_label_past_the_last_instruction_ends_the_path(self):
        # Arrange
        listing = program(end=BRANCH_TO_THE_END)

        # Act
        found = writetiming.gaps(listing)

        # Assert
        assert found == []


class TestPathsAcrossFunctions:
    def test_a_write_before_a_return_is_measured_against_the_callers_next(self):
        # Arrange
        both = program(callee=CALLEE_ENDING_ON_A_WRITE, caller=CALLER_WRITING_AT_ONCE)

        # Act
        found = writetiming.gaps(both)

        # Assert
        assert [(g.source, g.cycles, g.to_source) for g in found] == [("callee", 21, "caller")]

    def test_a_call_reaches_the_callees_first_write(self):
        # Arrange
        both = program(caller=CALLER_WRITING_THEN_CALLING, callee=CALLEE_ENDING_ON_A_WRITE)

        # Act
        found = writetiming.gaps(both)

        # Assert
        assert [(g.source, g.cycles, g.to_source) for g in found] == [("caller", 28, "callee")]

    def test_a_tail_jump_reaches_the_listed_functions_first_write(self):
        # Arrange
        both = program(caller=TAIL_JUMP_INTO_A_LISTED_FUNCTION, callee=CALLEE_ENDING_ON_A_WRITE)

        # Act
        found = writetiming.gaps(both)

        # Assert
        assert [(g.source, g.cycles, g.to_source) for g in found] == [("caller", 21, "callee")]

    def test_a_tail_jump_out_of_the_listings_returns_to_the_caller(self):
        # Arrange
        listing = program(tail=TAIL_JUMP_OUT_OF_THE_LISTINGS)

        # Act
        found = writetiming.gaps(listing)

        # Assert
        assert cycles(found) == [21]

    def test_tail_jumps_in_a_circle_settle_on_the_shortest_way_back(self):
        # Arrange
        listing = program(circle=TAIL_JUMPS_IN_A_CIRCLE)

        # Act
        found = writetiming.gaps(listing)

        # Assert
        assert [(g.first.address, g.second.address, g.cycles) for g in found] == [
            (0x06, 0x0B, 11 + 17 + 10 + 11)
        ]

    def test_a_return_after_a_data_label_still_reaches_the_caller(self):
        # Arrange
        listing = program(strings=DATA_LABEL_INSIDE_A_FUNCTION)

        # Act
        found = writetiming.gaps(listing)

        # Assert
        leaving = [(g.second.address, g.cycles) for g in found if g.first.address == 0]
        assert leaving == [(0x0B, 11 + 12 + 10)]


class TestTheWalkBudget:
    def test_branches_that_would_multiply_into_thousands_of_paths_still_settle(self):
        # Arrange
        listing = program(paths=branching(12))

        # Act
        found = writetiming.gaps(listing)

        # Assert
        assert cycles(found) == [11 + 12 * 7]

    def test_a_walk_that_cannot_settle_fails_rather_than_passing(self):
        # Arrange
        listing = program(paths=branching(2))

        # Act
        with pytest.raises(ValueError) as refused:
            writetiming.gaps(listing, budget=0)

        # Assert
        assert str(refused.value) == "the walk from 0x0010 in paths did not settle"


class TestDescribingAGap:
    def test_a_gap_names_where_it_is_and_what_it_measured(self):
        # Arrange
        found = writetiming.gaps(program(fall=NOT_TAKEN_PATH))

        # Act
        text = found[0].describe()

        # Assert
        assert text == (
            "fall: 18 T-states from data write at 0x0010 to data write at 0x0014, falling through"
        )

    def test_a_gap_into_another_listing_names_it(self):
        # Arrange
        found = writetiming.gaps(
            program(callee=CALLEE_ENDING_ON_A_WRITE, caller=CALLER_WRITING_AT_ONCE)
        )

        # Act
        text = found[0].describe()

        # Assert
        assert text == (
            "callee: 21 T-states from control write at 0x0000 to control write at 0x0003 "
            "in caller, around the loop"
        )
