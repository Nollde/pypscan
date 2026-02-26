"""
Terminal UI backend for PyPScan using Textual.

Install extra: pip install pypscan[tui]
"""
import datetime
import os

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.message import Message
    from textual.widgets import Header, Footer, Label, Static
except ImportError as exc:
    raise ImportError(
        "The TUI backend requires 'textual'. Install it with:\n"
        "    pip install pypscan[tui]\n"
        "or:\n"
        "    pip install textual"
    ) from exc

from .core import Scanner, ParametricIndex


# ---------------------------------------------------------------------------
# Image rendering via Pillow (optional)
# ---------------------------------------------------------------------------

def _render_image(path: str, width: int, height: int):
    """
    Render an image as half-block Unicode art using Rich Text.
    Each terminal cell row covers 2 pixel rows via the '▀' character:
    foreground = upper pixel colour, background = lower pixel colour.
    Returns a Rich Text object, or a plain string on error/missing dep.
    """
    try:
        from PIL import Image
        from rich.color import Color
        from rich.style import Style
        from rich.text import Text
    except ImportError:
        return f"[dim]Install pillow to preview images[/dim]\n{path}"

    if width <= 0 or height <= 0:
        return path

    try:
        img = Image.open(path).convert("RGB")
        # Scale to fill the available area (up OR down), maintaining aspect ratio.
        # Each terminal row covers 2 pixel rows via the half-block '▀' character.
        target_w = max(1, width)
        target_h = max(1, height * 2)
        img_w, img_h = img.size
        scale = min(target_w / img_w, target_h / img_h)
        img = img.resize(
            (max(1, round(img_w * scale)), max(1, round(img_h * scale))),
            Image.LANCZOS,
        )
        w, h = img.size
        pixels = img.load()

        text = Text(no_wrap=True)
        for row in range(0, (h // 2) * 2, 2):
            for col in range(w):
                r1, g1, b1 = pixels[col, row]
                r2, g2, b2 = pixels[col, row + 1] if row + 1 < h else (0, 0, 0)
                text.append(
                    "▀",
                    style=Style(
                        color=Color.from_rgb(r1, g1, b1),
                        bgcolor=Color.from_rgb(r2, g2, b2),
                    ),
                )
            text.append("\n")
        return text
    except Exception as exc:
        return f"[red]Error rendering image:[/red] {exc}\n{path}"


def _size_str(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 ** 2:.2f} MB"


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

class _OptionButton(Static):
    """
    A clickable label representing one parameter value.
    Replaces RadioButton to avoid Textual's RadioSet internal-state issues.
    """

    DEFAULT_CSS = """
    _OptionButton {
        height: 1;
        padding: 0 1;
        background: $surface-darken-1;
        color: $text-muted;
    }
    _OptionButton:hover {
        background: $surface-lighten-1;
        color: $text;
    }
    _OptionButton.active {
        background: #16a34a;
        color: #fff;
        text-style: bold;
    }
    """

    class Pressed(Message):
        def __init__(self, button: "_OptionButton") -> None:
            super().__init__()
            self.button = button

    def __init__(self, param: str, value: str, active: bool = False) -> None:
        super().__init__(str(value))
        self.param_name = param
        self.param_value = str(value)
        if active:
            self.add_class("active")

    def on_click(self) -> None:
        self.post_message(self.Pressed(self))


class _ParamPanel(Vertical):
    """Vertical panel showing clickable option buttons for one parameter."""

    DEFAULT_CSS = """
    _ParamPanel {
        width: auto;
        height: auto;
        min-width: 10;
        padding: 0 1;
        border: tall #16a34a;
    }
    _ParamPanel Label.param-title {
        text-style: bold;
        padding-bottom: 1;
        color: $text;
    }
    """

    def __init__(self, name: str, options: list, selected: str | None = None) -> None:
        super().__init__()
        self._param_name = name
        self._options = list(options)
        self._selected = selected or (options[0] if options else "")

    def compose(self) -> ComposeResult:
        yield Label(self._param_name, classes="param-title")
        for opt in self._options:
            yield _OptionButton(self._param_name, str(opt), str(opt) == str(self._selected))

    def set_selected(self, value: str) -> None:
        """Update visual selection without rebuilding buttons."""
        self._selected = str(value)
        for btn in self.query(_OptionButton):
            btn.set_class(btn.param_value == self._selected, "active")

    def rebuild(self, options: list, selected: str) -> None:
        """Replace all option buttons (for cross-filtering)."""
        self._options = list(options)
        self._selected = str(selected)
        for btn in self.query(_OptionButton):
            btn.remove()
        for opt in options:
            self.mount(_OptionButton(self._param_name, str(opt), str(opt) == self._selected))


class _ContentViewer(Static):
    """
    Shows file metadata and an inline preview (image or text).
    Image preview uses half-block Unicode art via Pillow.

    Inherits from Static so that update() is available.  Rendering is driven
    by on_resize (fired once layout is complete and on every terminal resize)
    rather than render() which is called before layout with size=(0,0).
    """

    DEFAULT_CSS = """
    _ContentViewer {
        height: 1fr;
        border: tall #16a34a;
        margin: 1 1;
        padding: 1 2;
        overflow: auto;
    }
    """

    def __init__(self) -> None:
        super().__init__("")
        self._path: str | None = None

    def display_path(self, path: str | None) -> None:
        self._path = path
        self._update_display()

    def on_resize(self) -> None:
        # Called by Textual once layout is known and on every terminal resize.
        self._update_display()

    def _update_display(self) -> None:
        from rich.console import Group
        from rich.text import Text

        path = self._path
        if path is None:
            self.update(Text("No file selected.", style="dim"))
            return

        if not os.path.exists(path):
            self.update(Text.from_markup(f"[red]File not found:[/red] {path}"))
            return

        try:
            st = os.stat(path)
            mtime = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
            info = Text.from_markup(
                f"[bold]Path:[/bold]     {path}\n"
                f"[bold]Size:[/bold]     {_size_str(st.st_size)}\n"
                f"[bold]Modified:[/bold] {mtime}\n"
            )
        except Exception as exc:
            self.update(Text.from_markup(f"[red]Error:[/red] {exc}"))
            return

        ext = os.path.splitext(path)[1].lower()
        if ext in {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif", ".webp"}:
            # content_size excludes border and padding — the true renderable area.
            # Only draw the image once we have a valid size (after first layout).
            w = self.content_size.width
            h = self.content_size.height
            if w > 0 and h > 4:
                preview = _render_image(path, w, h - 4)  # 4 rows reserved for info
                if isinstance(preview, str):
                    preview = Text.from_markup(preview)
                self.update(Group(info, preview))
            else:
                self.update(info)
            return

        if ext in {".txt", ""}:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(8192)
                self.update(Group(info, Text(content)))
            except Exception as exc:
                self.update(Group(info, Text.from_markup(f"[red]Cannot read:[/red] {exc}")))
            return

        self.update(info)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class TuiApp(App):
    """Textual application for the parametric file browser."""

    TITLE = "PyPScan"
    CSS = """
    App { accent-color: #16a34a; }

    Screen {
        layout: vertical;
    }
    #controls {
        height: auto;
        layout: horizontal;
        padding: 0;
        overflow-x: auto;
        overflow-y: hidden;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "rescan", "Rescan"),
    ]

    def __init__(self, index: ParametricIndex, regex: str, base_path: str) -> None:
        super().__init__()
        self._index = index
        self._regex = regex
        self._base_path = base_path
        self._selection: dict = {}

    def compose(self) -> ComposeResult:
        yield Header()
        options = self._index.get_options()
        self._selection = {k: v[0] for k, v in options.items() if v}
        with Horizontal(id="controls"):
            for param, values in options.items():
                yield _ParamPanel(param, values, selected=self._selection.get(param))
        yield _ContentViewer()
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_viewer()

    def on__option_button_pressed(self, event: _OptionButton.Pressed) -> None:
        btn = event.button
        param = btn.param_name
        value = btn.param_value

        # Update selection
        self._selection[param] = value

        # Update visual state of the clicked param's panel (no rebuild needed)
        panel = self._get_panel(param)
        if panel:
            panel.set_selected(value)

        # Rebuild other params' options for cross-filtering
        self._update_options(changed_param=param)
        self._refresh_viewer()

    def _get_panel(self, param: str) -> _ParamPanel | None:
        for panel in self.query(_ParamPanel):
            if panel._param_name == param:
                return panel
        return None

    def _update_options(self, changed_param: str) -> None:
        """Recompute and rebuild option buttons for every param except the one just changed."""
        for panel in self.query(_ParamPanel):
            param = panel._param_name
            if param == changed_param:
                continue
            excl = {k: v for k, v in self._selection.items() if k != param}
            new_opts = self._index.get_options(excl).get(param, [])
            if not new_opts:
                continue
            current = self._selection.get(param, "")
            if current not in [str(o) for o in new_opts]:
                current = str(new_opts[0])
                self._selection[param] = current
            panel.rebuild(new_opts, current)

    def _refresh_viewer(self) -> None:
        viewer = self.query_one(_ContentViewer)
        try:
            result = self._index.resolve(self._selection)
            path = result if isinstance(result, str) else None
        except KeyError:
            path = None
        viewer.display_path(path)

    def action_rescan(self) -> None:
        self._index.refresh(self._regex, self._base_path)
        self._refresh_viewer()
        self.notify("Rescan complete.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class TuiPScan:
    """
    Standalone terminal UI for PyPScan.

    Usage::

        from pypscan.tui import TuiPScan

        browser = TuiPScan(
            regex=r"param0_(?P<param0>.+)/param1_(?P<param1>\\d+)/file\\.png",
            base_path="demo/",
        )
        browser.run()
    """

    def __init__(self, regex: str, base_path: str = "./") -> None:
        self.regex = regex
        self.base_path = base_path
        scanner = Scanner(regex, base_path)
        self._index = ParametricIndex(scanner.scan())

    def run(self) -> None:
        """Launch the TUI application (blocking)."""
        TuiApp(self._index, self.regex, self.base_path).run()
