import abc
from typing import Dict, Generic, Type, TypeVar

import sqlalchemy.exc
import sqlalchemy.orm.scoping

from storage import connection
from storage.exceptions import RepositoryNotFoundException
from storage.repository import abstract

RepositoryT = TypeVar("RepositoryT", bound=abstract.AbstractRepository)


class AbstractUnitOfWork(abc.ABC, Generic[RepositoryT]):
    session: sqlalchemy.orm.Session
    repositories: Dict[Type[RepositoryT], RepositoryT]

    def __init__(self, *repository_classes: Type[RepositoryT]):
        self.repository_classes = repository_classes
        self.session = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "Session")
        self.repositories = {}

    @abc.abstractmethod
    def __enter__(self):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        ...

    @abc.abstractmethod
    def __exit__(self, *args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        ...

    def get_repo(self, repo_type: Type[RepositoryT]) -> RepositoryT:
        repo = self.repositories.get(repo_type)
        if repo is None:
            error_message = f"Cannot find the repository {repo_type.__name__} in uow"
            raise RepositoryNotFoundException(error_message)
        return repo

    @property
    def repository(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        raise AttributeError("The attribute 'repository' is not supported in uow")


class SQLAlchemyUnitOfWork(AbstractUnitOfWork[RepositoryT]):
    def __init__(
        self,
        *repository_classes: Type[RepositoryT],
        session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
    ):
        super().__init__(*repository_classes)

        self.scoped = session or connection.db.session

    def __enter__(self):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.session = self.scoped
        self.repositories = {
            repository_cls: repository_cls(self.scoped, is_in_uow=True)  # type: ignore[call-arg] # Too many arguments for "AbstractRepository" #type: ignore[call-arg] # Unexpected keyword argument "is_in_uow" for "AbstractRepository"
            for repository_cls in self.repository_classes
        }

        return self

    def __exit__(self, exn_type, exn_value, traceback):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # Rollback in case of an exception
        if exn_type is not None:
            self.rollback()
        self.repositories = self.session = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "Dict[Type[RepositoryT], RepositoryT]") #type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "Session")

    def rollback(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self.session.rollback()

    def commit(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self.session.commit()
