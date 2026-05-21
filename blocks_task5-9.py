import copy
import json
import math
import pathlib
import random
from datetime import date

import asyncio
import flet as ft

# Files
SAVE_FILE = pathlib.Path(__file__).parent / "2048_save.json"
SCORES_FILE = pathlib.Path(__file__).parent / "2048_scores.json"

# UI constants
N = 4
TILE_SIZE = 100
TILE_GAP = 10
PADDING = 20

BOARD_INNER = N * TILE_SIZE + (N + 0.5) * TILE_GAP
BOARD_OUTER = BOARD_INNER + 2 * TILE_GAP
WINDOW_WIDTH = BOARD_OUTER + 35 * PADDING
WINDOW_HEIGHT = BOARD_OUTER + 2 * PADDING + 260

# Game constants
WIN_VALUE = 2048

# Timer constants
TIME_LIMIT = 180  # seconds (3 minutes)

# Global runtime flags (wrapped in lists so closures can mutate)
time_left: list[int] = [TIME_LIMIT]
timer_running: list[bool] = [False]
timer_mode_enabled: list[bool] = [False]
bot_running: list[bool] = [False]

# Tile palettes and themes
LIGHT_TILES = {
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

DARK_TILES = {
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

THEMES = {
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


# Persistence helpers
def load_best_score() -> int:
    try:
        data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
        return int(data.get("best_score", 0))
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return 0


def save_best_score(score: int) -> None:
    SAVE_FILE.write_text(json.dumps({"best_score": score}, ensure_ascii=False), encoding="utf-8")


def save_state(game: "Game2048") -> None:
    data = {
        "best_score": game.best_score,
        "board": game.board,
        "score": game.score,
        "moves": game.moves,
    }
    SAVE_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load_state() -> dict | None:
    try:
        data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
        if "board" in data:
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return None


def load_scores() -> list[dict]:
    try:
        return json.loads(SCORES_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def add_score(score: int) -> bool:
    scores = load_scores()
    entry = {"score": int(score), "date": str(date.today())}
    scores.append(entry)
    scores.sort(key=lambda x: x["score"], reverse=True)
    scores = scores[:5]
    SCORES_FILE.write_text(json.dumps(scores, ensure_ascii=False), encoding="utf-8")
    return entry in scores


# Tile helpers
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


# Game logic
class Game2048:
    def __init__(self) -> None:
        self.best_score: int = load_best_score()
        self.win_value = WIN_VALUE
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
        self._score_recorded = False
        self.add_random_tile()
        self.add_random_tile()

    def undo(self) -> None:
        self.board = [row[:] for row in self._board_prev]
        self.score = self._score_prev
        self.moves = self._moves_prev
        self.state = "playing"

    def _compress(self, row: list[int]) -> list[int]:
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
                if row[i] >= self.win_value:
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


# Main UI
def main(page: ft.Page) -> None:
    # theme and runtime state
    current_theme: list[str] = ["light"]
    current_win: list[int] = [WIN_VALUE]

    def theme() -> dict:
        return THEMES[current_theme[0]]

    page.title = "2048"
    page.window.width = WINDOW_WIDTH
    page.window.height = WINDOW_HEIGHT
    page.window.resizable = False
    page.bgcolor = theme()["page_bg"]
    page.padding = ft.Padding.all(PADDING)

    game = Game2048()

    # --- Dialogs (placeholders) ---
    stats_dialog = ft.AlertDialog(
        title=ft.Text("Статистика гри", weight=ft.FontWeight.BOLD),
        content=ft.Text(""),
        actions=[ft.TextButton("Закрити", on_click=lambda e: close_stats_dialog(e))],
    )

    scores_dialog = ft.AlertDialog(
        title=ft.Text("Топ-5 результатів", weight=ft.FontWeight.BOLD),
        content=ft.Text(""),
        actions=[ft.TextButton("Закрити", on_click=lambda e: close_scores_dialog(e))],
    )

    page.overlay.append(stats_dialog)
    page.overlay.append(scores_dialog)

    def close_stats_dialog(e: ft.ControlEvent) -> None:
        stats_dialog.open = False
        page.update()

    def close_scores_dialog(e: ft.ControlEvent) -> None:
        scores_dialog.open = False
        page.update()

    # --- UI building blocks (create before handlers that reference them) ---
    # Timer text and switch
    timer_text = ft.Text("3:00", size=20, weight=ft.FontWeight.BOLD, color=theme()["txt"])
    timer_switch = ft.Switch(label="Режим на час (3:00)", value=False)

    # Title and status texts
    title_text = ft.Text("2048", size=48, weight=ft.FontWeight.BOLD, color=theme()["txt"])
    score_text = ft.Text(f"Очки: {game.score}", size=20, weight=ft.FontWeight.BOLD, color=theme()["txt"])
    best_text = ft.Text(value=f"Рекорд: {game.best_score}", size=14, color=theme()["txt"])
    moves_text = ft.Text(value=f"Ходів: {game.moves}", size=14, color=theme()["txt"])
    status_text = ft.Text("Стрілки - хід. BackSpace - Відміна ходу", size=16, color=theme()["txt"], text_align=ft.TextAlign.CENTER)
    progress_bar = ft.ProgressBar(value=0, width=BOARD_OUTER, color=ft.Colors.AMBER_600, bgcolor=ft.Colors.BROWN_100)

    # Helper to create tile container
    def make_tile(value: int) -> ft.Container:
        return ft.Container(
            width=TILE_SIZE,
            height=TILE_SIZE,
            bgcolor=tile_bg_color(value, theme()["tiles"]),
            border_radius=8,
            alignment=ft.Alignment.CENTER,
            content=ft.Text(
                value=str(value) if value else "",
                size=tile_font_size(value),
                weight=ft.FontWeight.BOLD,
                color=tile_text_color(value),
            ),
        )

    # Create tile controls grid
    tile_controls: list[list[ft.Container]] = [
        [make_tile(game.board[r][c]) for c in range(N)] for r in range(N)
    ]

    grid = ft.Container(
        content=ft.Column(
            controls=[ft.Row(controls=tile_controls[r], spacing=TILE_GAP) for r in range(N)],
            spacing=TILE_GAP,
        ),
        bgcolor=theme()["board_bg"],
        padding=ft.Padding.all(TILE_GAP),
        border_radius=8,
    )

    # Buttons (create placeholders; handlers will be assigned later)
    btn_style = ft.ButtonStyle(bgcolor={"": theme()["btn_bg"]}, color={"": ft.Colors.GREY_50})

    restart_btn = ft.Button(content="🔁", style=btn_style)
    stats_btn = ft.Button(content="📈", style=btn_style)
    continue_btn = ft.Button(content="▶️", style=btn_style, disabled=load_state() is None)
    hint_btn = ft.Button(content="💡", style=btn_style)
    themes_btn = ft.Button(content=theme()["icon"], style=btn_style)
    scores_btn = ft.Button(content="🏆", style=btn_style)
    bot_step_btn = ft.Button(content="Крок бота", style=btn_style)
    bot_auto_btn = ft.Button(content="Бот (авто)", style=btn_style)

    # Dropdown for win target
    win_dropdown = ft.Dropdown(
        value=str(WIN_VALUE),
        width=110,
        options=[
            ft.dropdown.Option("256"),
            ft.dropdown.Option("512"),
            ft.dropdown.Option("1024"),
            ft.dropdown.Option(str(WIN_VALUE)),
        ],
    )

    # --- Helper functions and async tasks ---

    async def timer_tick() -> None:
        while timer_running[0] and time_left[0] > 0:
            await asyncio.sleep(1)
            if not timer_running[0]:
                break
            time_left[0] -= 1
            mins, secs = divmod(time_left[0], 60)
            timer_text.value = f"{mins}:{secs:02d}"
            timer_text.color = ft.Colors.RED_600 if time_left[0] <= 30 else theme()["txt"]
            page.update()
            if game.state in ("won", "lost"):
                timer_running[0] = False
                break
        if timer_running[0] and time_left[0] == 0:
            timer_running[0] = False
            if game.state == "playing":
                game.state = "lost"
                if not getattr(game, "_score_recorded", False):
                    add_score(game.score)
                    game._score_recorded = True
                refresh_ui("Час вийшов!")

    def start_timer() -> None:
        timer_running[0] = True
        time_left[0] = TIME_LIMIT
        mins, secs = divmod(time_left[0], 60)
        timer_text.value = f"{mins}:{secs:02d}"
        timer_text.color = theme()["txt"]
        page.run_task(timer_tick)

    def stop_timer() -> None:
        timer_running[0] = False

    async def clear_hint_after_delay() -> None:
        await asyncio.sleep(2)
        for r in range(N):
            for c in range(N):
                tile_controls[r][c].border = None
        page.update()

    # Bot helpers
    def count_empty_after(move_fn) -> int:
        saved_board = copy.deepcopy(game.board)
        saved_score = game.score
        saved_moves = game.moves
        saved_board_prev = copy.deepcopy(game._board_prev)
        saved_score_prev = game._score_prev
        saved_moves_prev = game._moves_prev

        changed = move_fn()
        empty = sum(1 for r in range(N) for c in range(N) if game.board[r][c] == 0)

        # restore
        game.board = saved_board
        game.score = saved_score
        game.moves = saved_moves
        game._board_prev = saved_board_prev
        game._score_prev = saved_score_prev
        game._moves_prev = saved_moves_prev
        return empty if changed else -1

    def bot_step() -> bool:
        if game.state != "playing":
            return False
        candidates = [
            (game.move_left, count_empty_after(game.move_left)),
            (game.move_down, count_empty_after(game.move_down)),
            (game.move_right, count_empty_after(game.move_right)),
            (game.move_up, count_empty_after(game.move_up)),
        ]
        best_fn, best_score = max(candidates, key=lambda x: x[1])
        if best_score < 0:
            return False
        if best_fn():
            game.add_random_tile()
            game.check_lost()
            if game.state == "won":
                if timer_running[0]:
                    stop_timer()
                if not getattr(game, "_score_recorded", False):
                    add_score(game.score)
                    game._score_recorded = True
            refresh_ui()
            save_state(game)
            continue_btn.disabled = False
            return True
        return False

    async def bot_auto_run() -> None:
        while bot_running[0] and game.state == "playing":
            if not bot_step():
                break
            await asyncio.sleep(0.3)
        bot_running[0] = False
        bot_auto_btn.content = "Бот (авто)"
        page.update()

    # --- Event handlers (assign to buttons and controls) ---

    def on_restart(e: ft.ControlEvent) -> None:
        game.reset()
        # reset timer state
        if timer_mode_enabled[0]:
            start_timer()
        else:
            stop_timer()
            time_left[0] = TIME_LIMIT
            mins, secs = divmod(time_left[0], 60)
            timer_text.value = f"{mins}:{secs:02d}"
        refresh_ui("Стрілки або кнопки для ходу")

    def on_stats_click(e: ft.ControlEvent) -> None:
        stats_dialog.content = build_stats_content()
        stats_dialog.open = True
        page.update()

    def build_stats_content() -> ft.Column:
        labels = [
            ("Очки", str(game.score)),
            ("Рекорд", str(game.best_score)),
            ("Ходів", str(game.moves)),
            ("Стан гри", {"playing": "Йде гра", "won": "Перемога!", "lost": "Програш"}.get(game.state, "")),
        ]
        rows = [
            ft.Row(
                controls=[
                    ft.Text(label, size=14, color=ft.Colors.BROWN_500, width=130),
                    ft.Text(value, size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.BROWN_500),
                ]
            )
            for label, value in labels
        ]
        return ft.Column(controls=rows, spacing=8, tight=True)

    def on_continue(e: ft.ControlEvent) -> None:
        state = load_state()
        if state:
            game.board = state["board"]
            game.score = state["score"]
            game.moves = state["moves"]
            game.best_score = state.get("best_score", game.best_score)
            game.state = "playing"
            game._score_recorded = False
            continue_btn.disabled = True
            refresh_ui("Гру відновлено")

    def on_hint(e: ft.ControlEvent) -> None:
        if game.state != "playing":
            return
        cells = find_mergeable()
        for r in range(N):
            for c in range(N):
                tile_controls[r][c].border = ft.Border.all(3, ft.Colors.GREEN_400) if (r, c) in cells else None
        page.run_task(clear_hint_after_delay)
        page.update()

    def on_theme_toggle(e: ft.ControlEvent) -> None:
        current_theme[0] = "dark" if current_theme[0] == "light" else "light"
        apply_theme()
        refresh_ui()

    def on_scores_click(e: ft.ControlEvent) -> None:
        scores = load_scores()
        rows = [
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(i + 1))),
                    ft.DataCell(ft.Text(str(s["score"]), weight=ft.FontWeight.BOLD)),
                    ft.DataCell(ft.Text(s["date"])),
                ]
            )
            for i, s in enumerate(scores)
        ]
        table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("#")),
                ft.DataColumn(ft.Text("Очки"), numeric=True),
                ft.DataColumn(ft.Text("Дата")),
            ],
            rows=rows,
        )
        scores_dialog.content = table
        scores_dialog.open = True
        page.update()

    def on_timer_switch(e: ft.ControlEvent) -> None:
        timer_mode_enabled[0] = timer_switch.value
        if timer_mode_enabled[0]:
            start_timer()
        else:
            stop_timer()
            time_left[0] = TIME_LIMIT
            mins, secs = divmod(time_left[0], 60)
            timer_text.value = f"{mins}:{secs:02d}"
            timer_text.color = theme()["txt"]
            page.update()

    def on_win_change(e: ft.ControlEvent) -> None:
        try:
            current_win[0] = int(win_dropdown.value)
        except Exception:
            current_win[0] = WIN_VALUE
        game.reset()
        refresh_ui(f"Ціль: {current_win[0]}")

    def on_bot_step(e: ft.ControlEvent) -> None:
        bot_step()

    def on_bot_auto(e: ft.ControlEvent) -> None:
        if bot_running[0]:
            bot_running[0] = False
            bot_auto_btn.content = "Бот (авто)"
            page.update()
            return
        bot_running[0] = True
        bot_auto_btn.content = "Стоп бота"
        page.run_task(bot_auto_run)

    # Keyboard moves
    MOVES = {
        "Arrow Up": game.move_up,
        "Arrow Down": game.move_down,
        "Arrow Left": game.move_left,
        "Arrow Right": game.move_right,
    }

    def on_key(e: ft.KeyboardEvent) -> None:
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
            if game.state == "won":
                if timer_running[0]:
                    stop_timer()
                if not getattr(game, "_score_recorded", False):
                    add_score(game.score)
                    game._score_recorded = True
            refresh_ui()
            save_state(game)
            continue_btn.disabled = False

    page.on_keyboard_event = on_key

    # find mergeable helper
    def find_mergeable() -> set[tuple[int, int]]:
        result = set()
        for r in range(N):
            for c in range(N):
                v = game.board[r][c]
                if v == 0:
                    continue
                if c + 1 < N and game.board[r][c + 1] == v:
                    result.add((r, c))
                    result.add((r, c + 1))
                if r + 1 < N and game.board[r + 1][c] == v:
                    result.add((r, c))
                    result.add((r + 1, c))
        return result

    # apply theme function
    def apply_theme() -> None:
        t = theme()
        page.bgcolor = t["page_bg"]
        grid.bgcolor = t["board_bg"]
        new_style = ft.ButtonStyle(bgcolor={"": t["btn_bg"]}, color={"": ft.Colors.GREY_50})
        for btn in [restart_btn, themes_btn, stats_btn, continue_btn, hint_btn, scores_btn, bot_step_btn, bot_auto_btn]:
            btn.style = new_style
        for ctrl in [title_text, score_text, best_text, moves_text, status_text]:
            ctrl.color = t["txt"]
        themes_btn.content = t["icon"]
        win_dropdown.bgcolor = t["btn_bg"]
        win_dropdown.color = ft.Colors.GREY_50
        timer_text.color = t["txt"]

    # refresh UI
    def refresh_ui(msg: str = "") -> None:
        max_val = max(game.board[r][c] for r in range(N) for c in range(N))
        for r in range(N):
            for c in range(N):
                v = game.board[r][c]
                tile = tile_controls[r][c]
                tile.bgcolor = tile_bg_color(v, theme()["tiles"])
                tile.content.value = str(v) if v else ""
                tile.content.size = tile_font_size(v)
                tile.content.color = tile_text_color(v)
                tile.border = ft.Border.all(3, ft.Colors.AMBER_700) if v == max_val and v > 0 else None
        score_text.value = f"Очки: {game.score}"
        best_text.value = f"Рекорд: {game.best_score}"
        moves_text.value = f"Ходів: {game.moves}"
        if game.state == "won":
            status_text.value = "YOU WON!"
            if not getattr(game, "_score_recorded", False):
                add_score(game.score)
                game._score_recorded = True
            stop_timer()
        elif game.state == "lost":
            status_text.value = "GAME OVER"
            if not getattr(game, "_score_recorded", False):
                add_score(game.score)
                game._score_recorded = True
            stop_timer()
        else:
            status_text.value = msg or "Стрілки - хід. BackSpace - Відміна ходу"
        progress_bar.value = (math.log2(max_val) / math.log2(current_win[0])) if max_val and current_win[0] > 0 else 0
        if timer_mode_enabled[0]:
            mins, secs = divmod(time_left[0], 60)
            timer_text.value = f"{mins}:{secs:02d}"
            timer_text.color = ft.Colors.RED_600 if time_left[0] <= 30 else theme()["txt"]
        page.update()

    # Wire up button handlers (assign after handlers exist)
    restart_btn.on_click = on_restart
    stats_btn.on_click = on_stats_click
    continue_btn.on_click = on_continue
    hint_btn.on_click = on_hint
    themes_btn.on_click = on_theme_toggle
    scores_btn.on_click = on_scores_click
    bot_step_btn.on_click = on_bot_step
    bot_auto_btn.on_click = on_bot_auto
    timer_switch.on_change = on_timer_switch
    win_dropdown.on_text_change = on_win_change

    # Build header and layout
    header = ft.Row(
        controls=[
            title_text,
            win_dropdown,
            ft.Column(controls=[score_text, best_text, moves_text], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=4),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    buttons_row = ft.Row(
        controls=[restart_btn, stats_btn, continue_btn, hint_btn, bot_step_btn, bot_auto_btn, scores_btn],
        vertical_alignment=ft.MainAxisAlignment.SPACE_EVENLY,
    )

    status_row = ft.Row(controls=[status_text, themes_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    # Add to page
    page.add(
        ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                header,
                                buttons_row,
                                ft.Row(controls=[timer_text, timer_switch], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ],
                            spacing=8,
                        ),
                        grid,
                    ],
                    spacing=10,
                ),
                progress_bar,
                status_row,
            ],
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )

    # Finalize
    apply_theme()
    refresh_ui()

    # Start timer if switch was pre-enabled
    if timer_mode_enabled[0]:
        start_timer()


ft.run(main)
