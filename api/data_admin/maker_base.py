import abc
from typing import Any

from storage.connection import db


class _MakerBase(abc.ABC):
    spec_class = None

    def create_object_and_flush(self, spec: dict, *args: Any, **kwargs: Any) -> Any:
        obj = self.create_object(spec, *args, **kwargs)
        db.session.flush([obj])
        return obj

    @abc.abstractmethod
    def create_object(self, spec: dict, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError
