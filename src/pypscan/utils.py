from functools import partial

try:
    from tqdm.auto import tqdm
except ImportError:  # pragma: no cover
    def tqdm(iterable, **kwargs):  # type: ignore[misc]
        return iterable


POP_ERROR = object()


class SKDict(dict):
    """
    A dictionary with set-like keys. Taken from
    https://git.rwth-aachen.de/3pia/cms_analyses/tools/-/blob/master/data.py
    and modified.
    """
    @staticmethod
    def keyify(keyish):
        if isinstance(keyish, dict):
            keyish = keyish.items()
        keyish = frozenset(keyish)
        assert not any(isinstance(key, set) for key in keyish)
        return keyish

    def __init__(self, *args, **kwargs):
        super(SKDict, self).__init__()
        self.update(dict(*args, **kwargs))

    def update(self, *args, **kwargs):
        # assert 0 <= len(args) <= 1
        args += (kwargs,)
        for arg in args:
            for k, v in arg.items():
                self[k] = v

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def pop(self, key, default=POP_ERROR):
        try:
            val = self[key]
        except KeyError:
            if default is POP_ERROR:
                raise
            else:
                return default
        else:
            del self[key]
            return val

    def __getitem__(self, key):
        key = self.keyify(key)
        if key in self:
            return super(SKDict, self).__getitem__(key)
        ret = self.__class__({k - key: v for k, v in self.items() if key <= k})
        if not ret:
            raise KeyError(key)
        return ret

    def __setitem__(self, key, value):
        key = self.keyify(key)
        if isinstance(value, dict):
            for k, v in value.items():
                self[key | self.keyify(k)] = v
        else:
            super(SKDict, self).__setitem__(key, value)

    def __delitem__(self, key):
        key = self.keyify(key)
        if isinstance(self[key], dict):
            for k in self[key].keys():
                super().__delitem__(k | key)
        else:
            super().__delitem__(key)

    def copy(self):
        return self.__class__(self)

    def map(self, func, groups=None, prog=False):
        if groups is None:
            groups = self.keys()
        if isinstance(prog, str):
            prog = dict(desc=prog)
        if isinstance(prog, dict):
            prog = partial(tqdm, **prog)
        elif not prog:
            prog = lambda x: x
        return self.__class__({g: func(self[g]) for g in map(self.keyify, prog(groups))})

    @classmethod
    def zip(cls, *insts):
        assert all(isinstance(inst, cls) for inst in insts)
        keys = set()
        keys.update(*(inst.keys() for inst in insts))
        return cls({key: tuple(inst.get(key) for inst in insts) for key in keys})

    def only(self, *keys):
        return self.__class__({key: self[key] for key in keys})

    def dekey(self, *key):
        for k in self[key].keys():
            yield self[k]

    def items(self, *key):
        for k in (self[key] if key else self).keys():
            yield k, self[k]

    def mkeys(self, keys):
        data = [self[key] for key in keys]
        ads = set(isinstance(d, self.__class__) for d in data)
        if ads == {True}:
            keys = set(frozenset(d.keys()) for d in data)
            assert len(keys) == 1  # bad depth
            return list(keys)[0]
        elif ads == {False}:
            return ((),)
        else:
            raise RuntimeError("bad depth")

    def skeys(self):
        return map(frozenset, sorted(map(sorted, self.keys())))

    @property
    def pretty(self):
        return {"/".join(sorted(map(str, k))): v for k, v in self.items()}
