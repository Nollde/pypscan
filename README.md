# PyPScan
PyPScan is a parametric file browser.

Originally developed as "pscan" by the [VISPA Group](https://vispa.physik.rwth-aachen.de).

Available as a Jupyter widget, a terminal UI, and a web browser UI:

![output](https://github.com/user-attachments/assets/d7864b16-2a0f-4632-9fb7-75fd73730c27)

## Install

Base package (no UI dependencies):
```
pip install pypscan
```

With Jupyter support:
```
pip install pypscan[jupyter]
```

With terminal UI support:
```
pip install pypscan[tui]
```

Everything at once:
```
pip install pypscan[all]
```

## How it works

PyPScan walks a directory tree and extracts **named parameters** from file paths using a regular expression. Each `(?P<name>...)` group becomes a browsable dimension. The UI then lets you select values for each parameter interactively, filtering available options to only show valid combinations.

## Usage

### Jupyter notebook

```python
from pypscan import PyPScan

REGEX = (
    r"param0_(?P<param0>.+)"
    r"/param1_(?P<param1>\d+)"
    r"/file\.png"
)

browser = PyPScan(regex=REGEX, base_path="demo/")
browser.run()
```

Subclass `PyPScan` and override `display_content(path)` to add support for custom file formats.

### Terminal UI

```
pypscan --regex "param0_(?P<param0>.+)/param1_(?P<param1>\d+)/file\.png" \
        --base-path demo/ \
        --ui tui
```

Requires `pip install pypscan[tui]`. Press `q` to quit, `r` to rescan.

### Web browser UI

```
pypscan --regex "param0_(?P<param0>.+)/param1_(?P<param1>\d+)/file\.png" \
        --base-path demo/ \
        --ui web
```

Opens a local browser tab automatically. No extra dependencies beyond the base install.
Use `--port PORT` to change the default port (8765).

### Python API (no UI)

Access the scanner and index directly:

```python
from pypscan import Scanner, ParametricIndex

scanner = Scanner(
    regex=r"param0_(?P<param0>.+)/param1_(?P<param1>\d+)/file\.png",
    base_path="demo/",
)
index = ParametricIndex(scanner.scan())

# All available options
print(index.get_options())
# {'param0': ['a', 'b', 'c'], 'param1': ['0', '1', '2']}

# Filter options given a partial selection
print(index.get_options({"param0": "a"}))
# {'param1': ['0', '1', '2']}

# Resolve a full selection to a file path
path = index.resolve({"param0": "a", "param1": "0"})
```
