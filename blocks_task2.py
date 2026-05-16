import json
import pathlib
import random
import flet as ft

SAVE_FILE = pathlib.Path(__file__).parent / "2048_save.json"

N = 4
TILE_SIZE = 100
TILE_GAP = 10
PADDING = 20

BOARD_INNER = N * TILE_SIZE + (N + 0.5) * TILE_GAP
BOARD_OUTER = BOARD_INNER + 2 * TILE_GAP
WINDOW_WIDTH = BOARD_OUTER + 2 * PADDING
WINDOW_HEIGHT = BOARD_OUTER + 2 * PADDING + 150

WIN_VALUE = 2048

LIGHT_TILES: dict[int | str, ft.Colors] = {
    0: ft.Colors.BROWN_100,
    2: ft.Colors.ORANGE_50,
    4: ft.Colors.ORANGE_100,
    8: ft.Colors.ORANGE_300,
    16: ft.Colors.DEEP_ORANGE_300,
    32: ft.Colors.DEEP_ORANGE_400,
    64: ft.Colors.DEEP_ORANGE_500,
    128: ft.Colors.AMBER_300,
    256: ft.Colors.AMBER_400,
    512: ft.Colors.AMBER_500,
    1024: ft.Colors.AMBER_600,
    2048: ft.Colors.AMBER_700,
    "big": ft.Colors.BROWN_900,
}

DARK_TILES: dict[int | str, ft.Colors] = {
    0: ft.Colors.BLUE_900,
    2: ft.Colors.DEEP_PURPLE_700,
    4: ft.Colors.PURPLE_800,
    8: ft.Colors.PURPLE_600,
    16: ft.Colors.PURPLE_500,
    32: ft.Colors.RED_600,
    64: ft.Colors.RED_800,
    128: ft.Colors.ORANGE_600,
    256: ft.Colors.DEEP_ORANGE_700,
    512: ft.Colors.AMBER_700,
    1024: ft.Colors.YELLOW_700,
    2048: ft.Colors.GREEN_400,
    "big": ft.Colors.GREY_100,
}

THEMES: dict[str, dict] = {
    "light": {
        "tiles": LIGHT_TILES,
        "page_bg": ft.Colors.BROWN_50,
        "board_bg": ft.Colors.BROWN_200,
        "txt": ft.Colors.BROWN_500,
        "btn_bg": ft.Colors.BROWN_400,
        "icon": "🌙",
    },
    "dark": {
        "tiles": DARK_TILES,
        "page_bg": ft.Colors.BLUE_GREY_900,
        "board_bg": ft.Colors.INDIGO_900,
        "txt": ft.Colors.GREY_300,
        "btn_bg": ft.Colors.DEEP_PURPLE_700,
        "icon": "☀️",
    },
}


def load_best_score() -> int:
    try:
        data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
        return int(data.get("best_score", 0))
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return 0


def save_best_score(score: int) -> None:
    SAVE_FILE.write_text(
        json.dumps({"best_score": score}, ensure_ascii=False),
        encoding="utf-8",
    )


def tile_text_color(value: int) -> str:
    return ft.Colors.BROWN_500 if value in (0, 2, 4) else ft.Colors.GREY_50


def tile_font_size(value: int) -> int:
    if value < 100:
        return 36
    if value < 1000:
        return 28
    return 22


def tile_bg_color(value: int, tiles: dict) -> ft.Colors:
    return tiles.get(value, tiles["big"])


class Game2048:
    def __init__(self) -> None:
        self.best_score: int = load_best_score()
        self.reset()

    def add_random_tile(self) -> None:
        empty = [(r, c) for r in range(N) for c in range(N) if self.board[r][c] == 0]
        if empty:
            r, c = random.choice(empty)
            self.board[r][c] = 2 if random.random() < 0.9 else 4

    def check_lost(self) -> None:
        if self.state != "playing":
            return
        for r in range(N):
            for c in range(N):
                if self.board[r][c] == 0:
                    return
                if c + 1 < N and self.board[r][c] == self.board[r][c + 1]:
                    return
                if r + 1 < N and self.board[r][c] == self.board[r + 1][c]:
                    return
        self.state = "lost"

    def move_left(self) -> bool:
        self._save()
        changed = False
        for r in range(N):
            new_row, gained = self._process_row(self.board[r][:])
            self.score += gained
            if new_row != self.board[r]:
                changed = True
            self.board[r] = new_row
        return self._post_move(changed)

    def move_right(self) -> bool:
        self._save()
        changed = False
        for r in range(N):
            new_row, gained = self._process_row(self.board[r][::-1])
            new_row = new_row[::-1]
            self.score += gained
            if new_row != self.board[r]:
                changed = True
            self.board[r] = new_row
        return self._post_move(changed)

    def move_up(self) -> bool:
        self._save()
        changed = False
        for c in range(N):
            col = [self.board[r][c] for r in range(N)]
            new_col, gained = self._process_row(col)
            self.score += gained
            if new_col != col:
                changed = True
            for r in range(N):
                self.board[r][c] = new_col[r]
        return self._post_move(changed)

    def move_down(self) -> bool:
        self._save()
        changed = False
        for c in range(N):
            col = [self.board[r][c] for r in range(N)]
            new_col, gained = self._process_row(col[::-1])
            new_col = new_col[::-1]
            self.score += gained
            if new_col != col:
                changed = True
            for r in range(N):
                self.board[r][c] = new_col[r]
        return self._post_move(changed)

    def reset(self) -> None:
        self.board: list[list[int]] = [[0] * N for _ in range(N)]
        self._board_prev: list[list[int]] = [[0] * N for _ in range(N)]
        self.score = 0
        self._score_prev = 0
        self.moves = 0
        self._moves_prev = 0
        self.state = "playing"
        self.add_random_tile()
        self.add_random_tile()

    def undo(self) -> None:
        self.board = [row[:] for row in self._board_prev]
        self.score = self._score_prev
        self.moves = self._moves_prev
        self.state = "playing"

    @staticmethod
    def _compress(row: list[int]) -> list[int]:
        result = [x for x in row if x != 0]
        result += [0] * (N - len(result))
        return result

    def _merge(self, row: list[int]) -> tuple[list[int], int]:
        gained = 0
        merged = False
        for i in range(N - 1):
            if row[i] != 0 and row[i] == row[i + 1] and not merged:
                row[i] *= 2
                gained += row[i]
                row[i + 1] = 0
                merged = True
                if row[i] >= WIN_VALUE:
                    self.state = "won"
            else:
                merged = False
        return row, gained

    def _post_move(self, changed: bool) -> bool:
        if changed:
            self.moves += 1
            if self.score > self.best_score:
                self.best_score = self.score
                save_best_score(self.best_score)
        return changed

    def _process_row(self, row: list[int]) -> tuple[list[int], int]:
        row = self._compress(row)
        row, gained = self._merge(row)
        row = self._compress(row)
        return row, gained

    def _save(self) -> None:
        self._board_prev = [row[:] for row in self.board]
        self._score_prev = self.score
        self._moves_prev = self.moves


def main(page: ft.Page) -> None:
    current_theme: list[str] = ["light"]

    def theme() -> dict:
        return THEMES[current_theme[0]]

    page.title = "2048"
    page.window.width = WINDOW_WIDTH
    page.window.height = WINDOW_HEIGHT
    page.window.resizable = False
    page.bgcolor = theme()["page_bg"]
    page.padding = ft.Padding.all(PADDING)

    game = Game2048()

    stats_dialog = ft.AlertDialog(
        title=ft.Text("Статистика гри", weight=ft.FontWeight.BOLD),
        content=ft.Text(""),
        actions=[ft.Button("Закрити", on_click=lambda e: _close_dialog(e))],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def _close_dialog(e: ft.ControlEvent) -> None:
        stats_dialog.open = False
        page.update()

    page.overlay.append(stats_dialog)

    def build_stats_content() -> ft.Column:
        labels = [
            ("Очки", str(game.score)),
            ("Рекорд", str(game.best_score)),
            ("Ходів", str(game.moves)),
            (
                "Стан гри",
                {"playing": "Йде гра", "won": "Перемога!", "lost": "Програш"}.get(
                    game.state, ""
                ),
            ),
        ]
        rows = [
            ft.Row(
                controls=[
                    ft.Text(label, size=14, color=ft.Colors.BROWN_500, width=130),
                    ft.Text(
                        value,
                        size=14,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.BROWN_500,
                    ),
                ]
            )
            for label, value in labels
        ]
        return ft.Column(controls=rows, spacing=8, tight=True)

    def on_stats_click(e: ft.ControlEvent) -> None:
        stats_dialog.content = build_stats_content()
        stats_dialog.open = True
        page.update()

    def make_tile(value: int) -> ft.Container:
        return ft.Container(
            width=TILE_SIZE,
            height=TILE_SIZE,
            bgcolor=tile_bg_color(value, theme()["tiles"]),
            border_radius=8,
            alignment=ft.Alignment.CENTER,
            border=None,
            content=ft.Text(
                value=str(value) if value else "",
                size=tile_font_size(value),
                weight=ft.FontWeight.BOLD,
                color=tile_text_color(value),
            ),
        )

    tile_controls: list[list[ft.Container]] = [
        [make_tile(game.board[r][c]) for c in range(N)] for r in range(N)
    ]
    title_text = ft.Text(
        "2048",
        size=48,
        weight=ft.FontWeight.BOLD,
        color=theme()["txt"],
    )
    score_text = ft.Text(
        f"Очки: {game.score}",
        size=20,
        weight=ft.FontWeight.BOLD,
        color=theme()["txt"],
    )
    best_text = ft.Text(
        value=f"Рекорд: {game.best_score}", size=14, color=theme()["txt"]
    )
    moves_text = ft.Text(
        value=f"Ходів: {game.moves}", size=14, color=theme()["txt"]
    )
    status_text = ft.Text(
        "Стрілки - хід. R - заново. Z - відміна ходу",
        size=16,
        color=theme()["txt"],
        text_align=ft.TextAlign.CENTER,
    )

    def refresh_ui(msg: str = "") -> None:
        # знайти максимальне значення на полі
        max_val = max(game.board[r][c] for r in range(N) for c in range(N))

        for r in range(N):
            for c in range(N):
                v = game.board[r][c]
                tile = tile_controls[r][c]
                tile.bgcolor = tile_bg_color(v, theme()["tiles"])
                tile.content.value = str(v) if v else ""
                tile.content.size = tile_font_size(v)
                tile.content.color = tile_text_color(v)
                # підсвічування плитки з максимальним значенням рамкою
                tile.border = (
                    ft.Border.all(3, ft.Colors.AMBER_700)
                    if v == max_val and v > 0
                    else None
                )
        score_text.value = f"Очки: {game.score}"
        best_text.value = f"Рекорд: {game.best_score}"
        moves_text.value = f"Ходів: {game.moves}"
        if game.state == "won":
            status_text.value = "YOU WON!"
        elif game.state == "lost":
            status_text.value = "GAME OVER"
        else:
            status_text.value = msg or "Стрілки - хід. R - заново. Z - відміна ходу"
        page.update()

    refresh_ui()

    grid = ft.Container(
        content=ft.Column(
            controls=[ft.Row(controls=tile_controls[r], spacing=TILE_GAP) for r in range(N)],
            spacing=TILE_GAP,
        ),
        bgcolor=theme()["board_bg"],
        padding=ft.Padding.all(TILE_GAP),
        border_radius=8,
    )

    btn_style = ft.ButtonStyle(
        bgcolor={"": theme()["btn_bg"]}, color={"": ft.Colors.GREY_50}
    )

    def on_move(direction: str):
        fns = {
            "left": game.move_left,
            "right": game.move_right,
            "up": game.move_up,
            "down": game.move_down,
        }

        def handler(e: ft.ControlEvent) -> None:
            if game.state == "lost":
                return
            if fns[direction]():
                game.add_random_tile()
                game.check_lost()
                refresh_ui()

        return handler

    def on_undo(e: ft.ControlEvent) -> None:
        if game.state != "lost":
            game.undo()
            refresh_ui()

    def on_restart(e: ft.ControlEvent) -> None:
        game.reset()
        refresh_ui("Стрілки - хід. R - заново. Z - відміна ходу")

    def apply_theme() -> None:
        t = theme()
        page.bgcolor = t["page_bg"]
        grid.bgcolor = t["board_bg"]
        new_style = ft.ButtonStyle(
            bgcolor={"": t["btn_bg"]}, color={"": ft.Colors.GREY_50}
        )
        for btn in [restart_btn, themes_btn, stats_btn]:
            btn.style = new_style
        for ctrl in [title_text, score_text, best_text, moves_text, status_text]:
            ctrl.color = t["txt"]
        themes_btn.content = t["icon"]

    def on_theme_toggle(e: ft.ControlEvent) -> None:
        current_theme[0] = "dark" if current_theme[0] == "light" else "light"
        apply_theme()
        refresh_ui()

    restart_btn = ft.Button(
        content="🔁 New Game", on_click=on_restart, style=btn_style, width=145
    )
    stats_btn = ft.Button(
        content="📈 Stats", on_click=on_stats_click, style=btn_style, width=145
    )
    themes_btn = ft.Button(
        content=theme()["icon"], on_click=on_theme_toggle, style=btn_style
    )

    MOVES = {
        "Arrow Up": game.move_up,
        "Arrow Down": game.move_down,
        "Arrow Left": game.move_left,
        "Arrow Right": game.move_right,
    }

    def on_key(e: ft.KeyboardEvent) -> None:
        # R — нова гра
        if e.key == "R":
            game.reset()
            refresh_ui("Стрілки - хід. R - заново. Z - відміна ходу")
            return

        # Z — відміна ходу (аналог Backspace), тільки якщо гра не програна
        if e.key == "Z" and game.state != "lost":
            game.undo()
            refresh_ui()
            return

        # Backspace — відміна ходу
        if e.key == "Backspace" and game.state != "lost":
            game.undo()
            refresh_ui()
            return

        if game.state == "lost":
            return

        move_fn = MOVES.get(e.key)
        if move_fn and move_fn():
            game.add_random_tile()
            game.check_lost()
            refresh_ui()

    page.on_keyboard_event = on_key

    header = ft.Row(
        controls=[
            title_text,
            ft.Column(
                controls=[restart_btn, stats_btn],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            ft.Column(
                controls=[score_text, best_text, moves_text],
                horizontal_alignment=ft.CrossAxisAlignment.END,
                spacing=4,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )
    status_row = ft.Row(
        controls=[status_text, themes_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN
    )

    page.add(
        ft.Column(
            controls=[
                header,
                grid,
                status_row,
            ],
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )


if __name__ == "__main__":
    ft.run(main)
