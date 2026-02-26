import os
import warnings

from IPython.display import display
import ipywidgets as widgets

from .core import Scanner, ParametricIndex


class JupyterPScan:
    """
    Parametric file browser as a Jupyter widget UI.

    Usage::

        from pypscan import PyPScan

        browser = PyPScan(
            regex=r"param0_(?P<param0>.+)/param1_(?P<param1>\\d+)/file\\.png",
            base_path="demo/",
        )
        browser.run()

    Subclass and override :meth:`display_content` to add support for custom
    file types.
    """

    def __init__(self, regex: str, base_path: str = "./"):
        self.regex = regex
        self.base_path = base_path
        self._scanner = Scanner(regex, base_path)
        self._index = ParametricIndex(self._scanner.scan())
        self._controls: dict = {}
        self._output = widgets.Output()
        self._create_controls()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self):
        """Display the interactive widget."""
        header = widgets.HTML(
            '<div style="'
            "font-size:1.05em;font-weight:700;color:#16a34a;"
            "padding:2px 0 10px;border-bottom:2px solid #dcfce7;"
            "margin-bottom:6px;letter-spacing:.03em;"
            '">PyPScan</div>'
        )

        controls_box = widgets.VBox(
            list(self._controls.values()),
            layout=widgets.Layout(gap="2px"),
        )

        separator = widgets.HTML(
            '<div style="border-top:1px solid #e5e7eb;margin:8px 0"></div>'
        )

        ui = widgets.VBox(
            [header, controls_box, separator, self._output],
            layout=widgets.Layout(padding="12px 16px"),
        )

        for control in self._controls.values():
            control.observe(self._on_change, names="value")

        display(ui)
        self._show_current()

    def rescan(self):
        """Re-scan the filesystem and refresh controls."""
        self._index.refresh(self.regex, self.base_path)
        self._create_controls()

    def display_content(self, path: str):
        """
        Display the file at *path*.  Override to support additional formats.
        """
        try:
            lower = path.lower()
            if lower.endswith(".txt"):
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    display(f.read())
            elif lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")):
                # IPython handles these formats natively — no extra deps needed.
                from IPython.display import Image as IImage
                display(IImage(filename=path))
            elif lower.endswith((".tiff", ".pdf")):
                # TIFF and PDF need wand for conversion to a displayable format.
                try:
                    from wand.image import Image as WImage
                    display(WImage(filename=path))
                except ImportError:
                    print(
                        f"Install 'wand' to display "
                        f"{os.path.splitext(path)[1]} files.\nPath: {path}"
                    )
            else:
                print(f"Unsupported file type: {path}")
        except FileNotFoundError:
            print(f"File not found: {path}")
        except PermissionError:
            print(f"Permission denied: {path}")
        except Exception as exc:
            print(f"Error displaying {path}: {exc}")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _create_controls(self):
        options = self._index.get_options()
        self._controls = {
            key: widgets.ToggleButtons(
                description=key,
                options=values,
                style=widgets.ToggleButtonsStyle(button_width="auto"),
                layout=widgets.Layout(width="100%"),
            )
            for key, values in options.items()
        }

    def _current_selection(self, exclude: str | None = None) -> dict:
        return {
            k: ctrl.value
            for k, ctrl in self._controls.items()
            if k != exclude
        }

    def _show_current(self):
        """Resolve the current selection and display the file."""
        kwargs = {k: ctrl.value for k, ctrl in self._controls.items()}
        self._output.clear_output(wait=True)
        with self._output:
            try:
                result = self._index.resolve(kwargs)
            except KeyError:
                print("No file matches the current selection.")
                return
            if isinstance(result, str):
                self.display_content(result)
            else:
                print(f"Ambiguous selection; {len(result)} files match.")

    def _on_change(self, _change):
        self._update_options(_change)
        self._show_current()

    def _update_options(self, _change):
        """Recompute available options for each control based on the others."""
        for key, control in self._controls.items():
            current_value = control.value
            selection = self._current_selection(exclude=key)
            options_map = self._index.get_options(selection)
            new_options = options_map.get(key, [current_value])
            if not new_options:
                continue
            control.options = new_options
            if current_value in new_options:
                control.value = current_value
            else:
                control.value = new_options[0]
                warnings.warn(
                    f"Parameter '{key}' value '{current_value}' is no longer "
                    f"available; reset to '{new_options[0]}'.",
                    UserWarning,
                    stacklevel=2,
                )
