from abc import ABC, abstractmethod


class Converter(ABC):
    def __set_name__(self, owner, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.name = name

    def __set__(self, instance, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.convert(value)
        setattr(instance, self.name, value)

    def __get__(self, obj, objtype=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return getattr(obj, self.name)

    @abstractmethod
    def convert(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        ...
