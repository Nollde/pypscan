import re
import os
import warnings
from collections import defaultdict, OrderedDict

from .utils import SKDict


class Scanner:
    """Walks a directory tree and extracts parametric file paths via a regex."""

    def __init__(self, regex: str, base_path: str = "./"):
        if not re.compile(regex).groupindex:
            warnings.warn(
                "Regex has no named groups. Use (?P<name>...) to define parameters.",
                UserWarning,
                stacklevel=2,
            )
        self._regex = re.compile(regex)
        self.base_path = base_path

    def scan(self) -> SKDict:
        """Walk base_path and return an SKDict mapping param dicts -> file paths."""
        skdict = SKDict()
        warned_empty = False
        for root, _dirs, files in os.walk(self.base_path):
            for file in files:
                path = os.path.join(root, file)
                match = self._regex.search(path)
                if match is None:
                    continue
                groups = match.groupdict()
                if not groups:
                    if not warned_empty:
                        warnings.warn(
                            "Regex matched but produced no named groups; skipping.",
                            UserWarning,
                            stacklevel=2,
                        )
                        warned_empty = True
                    continue
                key = frozenset(groups.items())
                if key in skdict:
                    warnings.warn(
                        f"Duplicate parameter combination {dict(groups)!r}; "
                        f"overwriting previous entry.",
                        UserWarning,
                        stacklevel=2,
                    )
                skdict[groups] = path
        return skdict

    def rescan(self) -> SKDict:
        """Re-run the scan (picks up added/removed files)."""
        return self.scan()


class ParametricIndex:
    """
    Wraps an SKDict to provide parameter-aware filtering and option enumeration.
    """

    def __init__(self, skdict: SKDict):
        self._skdict = skdict
        self._cache: dict = {}

    @classmethod
    def from_scan(cls, regex: str, base_path: str = "./") -> "ParametricIndex":
        scanner = Scanner(regex, base_path)
        return cls(scanner.scan())

    def all_params(self) -> list:
        """Return sorted list of all parameter names."""
        params: set = set()
        for key in self._skdict.keys():
            for name, _ in key:
                params.add(name)
        return sorted(params)

    def get_options(self, selection: dict | None = None) -> dict:
        """
        Return {param: sorted([values, ...])} compatible with *selection*.
        If selection is None or empty, returns all options.
        """
        selection = selection or {}
        cache_key = frozenset(selection.items())
        if cache_key in self._cache:
            return self._cache[cache_key]

        if selection:
            try:
                subset = self._skdict[selection]
            except KeyError:
                subset = SKDict()
        else:
            subset = self._skdict

        opts: dict = defaultdict(set)
        for key in subset.keys():
            for name, value in key:
                opts[name].add(value)

        result = OrderedDict(
            (k, sorted(v)) for k, v in sorted(opts.items())
        )
        self._cache[cache_key] = result
        return result

    def resolve(self, selection: dict):
        """
        Given a full selection dict, return the file path (str).
        If selection is partial, returns a sub-SKDict.
        Raises KeyError if no match.
        """
        return self._skdict[selection]

    def invalidate_cache(self):
        self._cache.clear()

    def refresh(self, regex: str, base_path: str):
        """Re-scan and rebuild the index."""
        scanner = Scanner(regex, base_path)
        self._skdict = scanner.scan()
        self.invalidate_cache()
