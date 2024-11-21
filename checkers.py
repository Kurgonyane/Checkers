from dataclasses import dataclass
from enum import Enum
import re
from copy import deepcopy

# этот импорт нужен, чтобы при вводе текста в input() можно было использовать стрелки и т.п.
import readline  # noqa: F401


class Color(Enum):
    WHITE = 1
    BLACK = 2


class PieceType(Enum):
    MAN = 1
    KING = 2


@dataclass
class Piece:
    color: Color
    type: PieceType


class MoveType(Enum):
    JUMP = 1
    RESIGN = 2
    DRAW = 3
    REJECT_DRAW = 4


@dataclass
class Jump:
    start_position: str
    end_position: str


@dataclass
class Move:
    color: Color
    type: MoveType
    jumps: list[Jump]


class GameResult(Enum):
    WHITE_WON = 1
    WHITE_WON_BY_RESIGN = 2
    BLACK_WON = 3
    BLACK_WON_BY_RESIGN = 4
    DRAW = 5


@dataclass
class PossibleMove:
    start: int
    end: int
    beaten: int | None
    promotion: bool


class CheckersException(Exception):
    """Шашечная ошибка."""


class Game:
    ROWS = list("12345678")
    COLUMNS = list("abcdefgh")

    PIECES_COUNT = 12

    LINES = [
        # большая дорога
        [0, 4, 9, 13, 18, 22, 27, 31],
        # двойник
        [3, 6, 10, 13, 17, 20, 24],
        [7, 11, 14, 18, 21, 25, 28],
        [3, 7],
        [24, 28],
        # тройник
        [1, 5, 10, 14, 19, 23],
        [8, 12, 17, 21, 26, 30],
        [1, 4, 8],
        [23, 27, 30],
        # косяк
        [2, 6, 11, 15],
        [16, 20, 25, 29],
        [2, 5, 9, 12, 16],
        [15, 19, 22, 26, 29],
    ]

    def __init__(self) -> None:
        self._moves = []
        self._boards = []
        self._result = None

    @staticmethod
    def _validate_position(position: str) -> None:
        if not re.match(r"^[a-h][1-8]$", position):
            raise CheckersException(f"Invalid position: {position}")

        column, row = position
        column_i = Game.COLUMNS.index(column)
        row_i = Game.ROWS.index(row)

        if column_i % 2 != row_i % 2:
            raise CheckersException(f"Invalid position: {position} (white cell)")

    @staticmethod
    def parse_move(color: Color, move_str: str) -> Move:
        move_str = move_str.strip().lower()
        if move_str == "resign":
            return Move(color=color, type=MoveType.RESIGN, jumps=[])
        if move_str == "draw":
            return Move(color=color, type=MoveType.DRAW, jumps=[])
        if move_str in ["reject", "reject draw", "reject_draw"]:
            return Move(color=color, type=MoveType.REJECT_DRAW, jumps=[])

        if "-" in move_str and ":" in move_str:
            raise CheckersException("Invalid move, should be either '-' or ':'")

        positions = [p.strip() for p in move_str.replace(":", "-").split("-")]

        for position in positions:
            Game._validate_position(position)

        if len(positions) < 2:
            raise CheckersException("Invalid move, should be at least two positions")

        jumps = [Jump(start, end) for start, end in zip(positions, positions[1:])]

        return Move(
            color=color,
            type=MoveType.JUMP,
            jumps=jumps,
        )

    def _make_initial_board(self) -> list[Piece]:
        # храним только черные клетки доски 8х8
        initial_board = [None for _ in range(8 * 8 // 2)]

        for i in range(self.PIECES_COUNT):
            # белые в начале доски
            initial_board[i] = Piece(Color.WHITE, PieceType.MAN)
            # черные в конце доски
            initial_board[-i - 1] = Piece(Color.BLACK, PieceType.MAN)

        return initial_board

    def whose_turn(self) -> Color:
        return Color.WHITE if len(self._moves) % 2 == 0 else Color.BLACK

    def is_over(self) -> bool:
        return self._result is not None

    def get_pieces_count(self) -> tuple[int, int]:
        board = self._boards[-1] if self._boards else self._make_initial_board()
        white_count = sum(1 for piece in board if piece and piece.color == Color.WHITE)
        black_count = sum(1 for piece in board if piece and piece.color == Color.BLACK)
        return white_count, black_count

    def get_beaten_pieces_count(self) -> tuple[int, int]:
        white, black = self.get_pieces_count()
        return (self.PIECES_COUNT - white, self.PIECES_COUNT - black)

    def _is_last_line_for_color(self, color: Color, position: int) -> bool:
        return (color == Color.BLACK and position < 4) or (
            color == Color.WHITE and position >= 28
        )

    def _get_available_moves_for_man(
        self, board: list[Piece], position: int, beaten_pieces: list[int]
    ) -> list[PossibleMove]:
        moves = []
        color = board[position].color

        # сначала ищем возможности атаки вокруг шашки
        for line in self.LINES:
            if position not in line:
                continue
            i = line.index(position)
            if (
                i >= 2
                and board[line[i - 1]]
                and board[line[i - 1]].color != board[position].color
                and not board[line[i - 2]]
                and line[i - 1] not in beaten_pieces
            ):
                moves.append(
                    PossibleMove(
                        start=position,
                        end=line[i - 2],
                        beaten=line[i - 1],
                        promotion=self._is_last_line_for_color(color, line[i - 2]),
                    )
                )
            if (
                i < len(line) - 2
                and board[line[i + 1]]
                and board[line[i + 1]].color != board[position].color
                and not board[line[i + 2]]
                and line[i + 1] not in beaten_pieces
            ):
                moves.append(
                    PossibleMove(
                        start=position,
                        end=line[i + 2],
                        beaten=line[i + 1],
                        promotion=self._is_last_line_for_color(color, line[i + 2]),
                    )
                )

        # затем обычные ходы
        # белые шашки ходят по возрастанию индексов, черные - по убыванию
        for line in self.LINES:
            if position not in line:
                continue

            i = line.index(position)
            if color == Color.WHITE and i < len(line) - 1 and not board[line[i + 1]]:
                moves.append(
                    PossibleMove(
                        start=position,
                        end=line[i + 1],
                        beaten=None,
                        promotion=self._is_last_line_for_color(color, line[i + 1]),
                    )
                )
            elif color == Color.BLACK and i >= 1 and not board[line[i - 1]]:
                moves.append(
                    PossibleMove(
                        start=position,
                        end=line[i - 1],
                        beaten=None,
                        promotion=self._is_last_line_for_color(color, line[i - 1]),
                    )
                )

        return moves

    def _get_available_moves_for_king(
        self, board: list[Piece], position: int, beaten_pieces: list[int]
    ) -> list[PossibleMove]:
        moves = []

        for line in self.LINES:
            if position not in line:
                continue

            i = line.index(position)

            # ищем вверх
            for j in range(i + 1, len(line)):
                if not board[line[j]]:
                    # ход без боя
                    moves.append(
                        PossibleMove(
                            start=position,
                            end=line[j],
                            beaten=None,
                            promotion=False,
                        )
                    )
                elif board[line[j]].color == board[position].color:
                    # встретили шашку своего цвета -- её перепрыгивать нельзя, прекращаем поиск в эту сторону
                    break
                elif board[line[j]].color != board[position].color:
                    # встретили шашку противника

                    # если её уже били, то прекращаем поиск в эту сторону
                    if line[j] in beaten_pieces:
                        break

                    # иначе ищем свободные клетки за ней
                    for k in range(j + 1, len(line)):
                        if board[line[k]]:
                            # встретили любую шашку -- дальше нельзя
                            break
                        moves.append(
                            PossibleMove(
                                start=position,
                                end=line[k],
                                beaten=line[j],
                                promotion=False,
                            )
                        )
                    # дальше одной шашки не бьём, поэтому после первой встреченной шашки в любом случае прекращаем поиск
                    break

            # ищем вниз
            for j in range(i - 1, -1, -1):
                if not board[line[j]]:
                    # ход без боя
                    moves.append(
                        PossibleMove(
                            start=position,
                            end=line[j],
                            beaten=None,
                            promotion=False,
                        )
                    )
                elif board[line[j]].color == board[position].color:
                    # встретили шашку своего цвета -- её перепрыгивать нельзя, прекращаем поиск в эту сторону
                    break
                elif board[line[j]].color != board[position].color:
                    # встретили шашку противника

                    # если её уже били, то прекращаем поиск в эту сторону
                    if line[j] in beaten_pieces:
                        break

                    # иначе ищем свободные клетки за ней
                    for k in range(j - 1, -1, -1):
                        if board[line[k]]:
                            # встретили любую шашку -- дальше нельзя
                            break
                        moves.append(
                            PossibleMove(
                                start=position,
                                end=line[k],
                                beaten=line[j],
                                promotion=False,
                            )
                        )
                    # дальше одной шашки не бьём, поэтому после первой встреченной шашки в любом случае прекращаем поиск
                    break

        return moves

    def _get_available_moves(
        self, board: list[Piece], position: int, beaten_pieces: list[int]
    ) -> list[PossibleMove]:
        piece = board[position]
        moves = []

        if piece is None:
            return moves

        if piece.type == PieceType.MAN:
            moves = self._get_available_moves_for_man(board, position, beaten_pieces)
        elif piece.type == PieceType.KING:
            moves = self._get_available_moves_for_king(board, position, beaten_pieces)
        else:
            raise CheckersException(f"Unknown piece type: {piece.type}")

        # если среди ходов есть рубящие ходы, то все остальные нужно убрать
        if any(move.beaten is not None for move in moves):
            moves = [move for move in moves if move.beaten is not None]

        return moves

    def _get_all_available_moves(
        self, board: list[Piece], color: Color
    ) -> list[PossibleMove]:
        moves = []

        for i, piece in enumerate(board):
            if piece is None or piece.color != color:
                continue
            moves.extend(self._get_available_moves(board, i, []))

        # если среди ходов есть рубящие ходы, то все остальные нужно убрать
        if any(move.beaten is not None for move in moves):
            moves = [move for move in moves if move.beaten is not None]

        return moves

    def _check_if_game_is_over(self) -> GameResult | None:
        board = self._boards[-1]

        # у одного из противников закончились ходы
        white_moves = self._get_all_available_moves(board, Color.WHITE)
        if not white_moves:
            return GameResult.BLACK_WON

        black_moves = self._get_all_available_moves(board, Color.BLACK)
        if not black_moves:
            return GameResult.WHITE_WON

        # TODO: сделать правила автоматической ничьей

        return None

    def _translate_str_position_to_internal(self, position: str) -> int:
        column, row = position
        column_i = self.COLUMNS.index(column)
        row_i = self.ROWS.index(row)
        return (row_i * 4) + (column_i // 2)

    def _translate_internal_position_to_str(self, position: int) -> int:
        row = position // 4
        column = (position % 4) * 2 + (1 if row % 2 == 1 else 0)
        return f"{self.COLUMNS[column]}{self.ROWS[row]}"

    def move(self, move: Move) -> None:
        if self.whose_turn() != move.color:
            raise CheckersException("It's not your turn")

        if self.is_over():
            raise CheckersException("Game is over")

        if move.type == MoveType.RESIGN:
            self._moves.append(move)
            self._result = (
                GameResult.BLACK_WON_BY_RESIGN
                if move.color == Color.WHITE
                else GameResult.WHITE_WON_BY_RESIGN
            )
            return

        prev_move = self._moves[-1] if self._moves else None

        if move.type == MoveType.DRAW:
            # если предыдущий ход уже был предложением ничьей, то завершить игру
            if prev_move and prev_move.type == MoveType.DRAW:
                self._moves.append(move)
                self._result = GameResult.DRAW
                return

            # иначе передать предложение ничьей противнику
            self._moves.append(move)
            return

        if move.type == MoveType.REJECT_DRAW:
            # если предыдущий ход был предложением ничьей, то отказываем в ничьей и продолжаем игру
            if prev_move and prev_move.type == MoveType.DRAW:
                self._moves.append(move)
                return
            else:
                raise CheckersException("No draw to reject")

        # если предыдущий ход был предложением ничьей, то нужно либо принять предложение, либо отказаться
        # другие ходы запрещены
        if prev_move and prev_move.type == MoveType.DRAW:
            raise CheckersException("You have to accept or reject draw")

        board = (
            deepcopy(self._boards[-1]) if self._boards else self._make_initial_board()
        )

        # первый "прыжок" в ходу нужно провалидировать отдельно, чтобы убедиться, что
        # при наличии атак пользователь не делает других ходов
        all_available_moves = self._get_all_available_moves(board, move.color)
        all_available_moves_p = [(m.start, m.end) for m in all_available_moves]
        if (
            self._translate_str_position_to_internal(move.jumps[0].start_position),
            self._translate_str_position_to_internal(move.jumps[0].end_position),
        ) not in all_available_moves_p:
            possible_moves_str = ", ".join(
                f"{self._translate_internal_position_to_str(m.start)}{":" if m.beaten else "-"}{self._translate_internal_position_to_str(m.end)}"
                for m in all_available_moves
            )
            raise CheckersException(
                f"Invalid move. Possible moves: {possible_moves_str}."
            )

        beaten_pieces = []

        for jump in move.jumps:
            start = self._translate_str_position_to_internal(jump.start_position)
            end = self._translate_str_position_to_internal(jump.end_position)

            available_moves = self._get_available_moves(board, start, beaten_pieces)
            available_moves_d = {m.end: m for m in available_moves}
            if end not in available_moves_d:
                raise CheckersException(
                    f"Invalid move: {jump.start_position} - {jump.end_position}"
                )

            possible_move = available_moves_d[end]
            if possible_move.beaten is not None:
                beaten_pieces.append(possible_move.beaten)

            board[end] = board[start]
            if possible_move.promotion:
                board[end].type = PieceType.KING
            board[start] = None

        # если последним действием было рубление, то проверим не нужно ли продолжить рубить
        if possible_move.beaten:
            available_moves = self._get_available_moves(board, end, beaten_pieces)
            if any(move.beaten is not None for move in available_moves):
                raise CheckersException(
                    "You have to continue attack, you can't stop here"
                )

        for beaten_piece in beaten_pieces:
            board[beaten_piece] = None

        self._boards.append(board)
        self._moves.append(move)

        self._result = self._check_if_game_is_over()

    def _print_piece(self, piece: Piece) -> str:
        if piece.color == Color.WHITE:
            return "🟡" if piece.type == PieceType.MAN else "💛"
        elif piece.color == Color.BLACK:
            return "🔵" if piece.type == PieceType.MAN else "💙"

    def _print_line(
        self,
        line_number: int,
        c1: Piece | None,
        c2: Piece | None,
        c3: Piece | None,
        c4: Piece | None,
        beaten_color: Color | None = None,
        beaten_count: int | None = None,
    ) -> None:
        result = f"{line_number} │"

        offset_left = line_number % 2 == 0

        white_cell = "  "
        black_cell = "██"

        if offset_left:
            result += white_cell

        if c1:
            result += self._print_piece(c1)
        else:
            result += black_cell
        result += white_cell

        if c2:
            result += self._print_piece(c2)
        else:
            result += black_cell
        result += white_cell

        if c3:
            result += self._print_piece(c3)
        else:
            result += black_cell
        result += white_cell

        if c4:
            result += self._print_piece(c4)
        else:
            result += black_cell

        if not offset_left:
            result += white_cell

        result += f"│ {line_number}"

        if beaten_color is not None:
            result += (
                " "
                + (self._print_piece(Piece(color=beaten_color, type=PieceType.MAN)))
                * beaten_count
            )

        print(result)

    def print_current_board(self):
        board = self._boards[-1] if self._boards else self._make_initial_board()
        white_beaten, black_beaten = self.get_beaten_pieces_count()

        print("   a b c d e f g h    ")
        print("  ┌────────────────┐  ")
        for i in reversed(range(0, 32, 4)):
            line_number = i // 4 + 1

            beaten_color = None
            beaten_count = None

            if line_number == 1:
                beaten_color = Color.BLACK
                beaten_count = black_beaten
            elif line_number == 8:
                beaten_color = Color.WHITE
                beaten_count = white_beaten

            self._print_line(
                line_number,
                board[i],
                board[i + 1],
                board[i + 2],
                board[i + 3],
                beaten_color=beaten_color,
                beaten_count=beaten_count,
            )
        print("  └────────────────┘  ")
        print("   a b c d e f g h   ")


if __name__ == "__main__":
    g = Game()

    while not g.is_over():
        g.print_current_board()

        print()
        color = "🟡" if g.whose_turn() == Color.WHITE else "🔵"
        move_str = input(f"> {color} Enter your move: ")

        if move_str.lower().startswith("_av"):
            print("Available moves:")
            board = g._boards[-1] if g._boards else g._make_initial_board()
            for move in g._get_all_available_moves(board, g.whose_turn()):
                print(
                    f" - {g._print_piece(board[move.start])} "
                    f"{g._translate_internal_position_to_str(move.start)}{':' if move.beaten else '-'}{g._translate_internal_position_to_str(move.end)}"
                )
            print()
            continue

        try:
            move = g.parse_move(g.whose_turn(), move_str)
            g.move(move)
        except CheckersException as e:
            print("💥 Error!", e.args[0])
            print("Try again.")

    print("Game ended:", g._result.name)
