import pytest

from checkers import Game, Color, MoveType, Move, Jump, CheckersException


class TestFlatBoardGameParseMove:
    def test_resign(self) -> None:
        # arrange
        color = Color.WHITE
        move_str = "Resign"

        # act
        move = Game.parse_move(color, move_str)

        # assert
        assert move == Move(color=color, type=MoveType.RESIGN, jumps=[])

    def test_draw(self) -> None:
        # arrange
        color = Color.WHITE
        move_str = "draW"

        # act
        move = Game.parse_move(color, move_str)

        # assert
        assert move == Move(color=color, type=MoveType.DRAW, jumps=[])

    @pytest.mark.parametrize("move_str", ["Reject", "reject draw", "REJECT_DRAW"])
    def test_reject_draw(self, move_str: str) -> None:
        # arrange
        color = Color.WHITE

        # act
        move = Game.parse_move(color, move_str)

        # assert
        assert move == Move(color=color, type=MoveType.REJECT_DRAW, jumps=[])

    def test_mixing_colon_and_dash(self) -> None:
        # arrange
        color = Color.WHITE
        move_str = "a1-b2:c3"

        # act & assert
        with pytest.raises(
            CheckersException, match=r"Invalid move, should be either '-' or ':'"
        ):
            Game.parse_move(color, move_str)

    @pytest.mark.parametrize(
        "move_str", ["a0 - a1", "a9:a1", "z1:z2", "aa:bb", "99-88"]
    )
    def test_invalid_position(self, move_str: str) -> None:
        # arrange
        color = Color.WHITE

        # act & assert
        with pytest.raises(CheckersException, match=r"Invalid position:"):
            Game.parse_move(color, move_str)

    @pytest.mark.parametrize(
        "move_str",
        [
            *(f"{column}{row} - a1" for row in list("1357") for column in list("bdfh")),
            *(f"{column}{row} - a1" for row in list("2468") for column in list("aceg")),
        ],
    )
    def test_white_cell_is_invalid(self, move_str: str) -> None:
        # arrange
        color = Color.WHITE

        # act & assert
        with pytest.raises(CheckersException, match=r"Invalid position:"):
            Game.parse_move(color, move_str)

    def test_short_move_is_invalid(self) -> None:
        # arrange
        color = Color.WHITE
        move_str = "a1"

        # act & assert
        with pytest.raises(
            CheckersException, match=r"Invalid move, should be at least two positions"
        ):
            Game.parse_move(color, move_str)

    @pytest.mark.parametrize(
        ("move_str", "expected_jumps"),
        [
            ("A1-B2", [Jump("a1", "b2")]),
            ("a1 : b2", [Jump("a1", "b2")]),
            ("A1:b2:c3:d4", [Jump("a1", "b2"), Jump("b2", "c3"), Jump("c3", "d4")]),
            # переберем все черные клетки
            *(
                (f"{column}{row} - a1", [Jump(f"{column}{row}", "a1")])
                for row in list("2468")
                for column in list("bdfh")
            ),
            *(
                (f"{column}{row} :a1", [Jump(f"{column}{row}", "a1")])
                for row in list("1357")
                for column in list("aceg")
            ),
        ],
    )
    def test_valid_moves(self, move_str: str, expected_jumps: list[Jump]) -> None:
        # arrange
        color = Color.WHITE

        # act
        move = Game.parse_move(color, move_str)

        # assert
        assert move == Move(color=color, type=MoveType.JUMP, jumps=expected_jumps)
