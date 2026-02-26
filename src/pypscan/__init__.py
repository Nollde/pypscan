from .core import Scanner, ParametricIndex

__all__ = ["PyPScan", "JupyterPScan", "Scanner", "ParametricIndex"]


def __getattr__(name: str):
    """Lazy-load Jupyter-dependent classes to avoid hard import of IPython."""
    if name in ("PyPScan", "JupyterPScan"):
        from .jupyter import JupyterPScan as _JupyterPScan
        # Cache in module globals so subsequent accesses are fast
        globals()["JupyterPScan"] = _JupyterPScan
        globals()["PyPScan"] = _JupyterPScan
        return _JupyterPScan
    raise AttributeError(f"module 'pypscan' has no attribute {name!r}")
