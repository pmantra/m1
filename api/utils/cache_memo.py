import threading
from typing import Any, Callable, Hashable


class memodict(dict):
    func: Callable[[Hashable], Any]

    def __init__(self, func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.func = func
        self.get_lock = threading.RLock()
        self.del_lock = threading.Lock()
        super().__init__()

    def __missing__(self, key):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with self.get_lock:
            if self.__contains__(key):
                # value could be computed before the lock was acquired
                return self[key]
            else:
                # do the calculation and release the lock
                return self.setdefault(key, self.func(key))

    def __delitem__(self, key):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with self.del_lock:
            if self.__contains__(key):
                super().__delitem__(key)
