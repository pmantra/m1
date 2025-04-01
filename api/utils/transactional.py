from sqlalchemy import event
from sqlalchemy.orm import Session

from storage.connection import db
from utils import log

logger = log.logger(__name__)


class OnSuccessfulCommitManager:
    def __init__(self) -> None:
        self.to_execute = {}

        event.listen(Session, "after_commit", self._on_after_commit)
        event.listen(
            Session, "after_transaction_end", self._on_receive_after_transaction_end
        )

    def _on_after_commit(self, session, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        tx_id = id(db.session().transaction)
        if tx_id in self.to_execute:
            logger.info(
                "Executing callbacks after commit",
                tx_id=tx_id,
            )
            for [func, func_args, func_kwargs] in self.to_execute.pop(tx_id):
                func(*func_args, **func_kwargs)

    def _on_receive_after_transaction_end(self, session, transaction):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        tx_id = id(transaction)
        if tx_id in self.to_execute:
            self.to_execute.pop(tx_id)
            logger.info(
                "Removed callbacks after transaction end",
                tx_id=tx_id,
            )

    def register(self, func, *func_args, **func_kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        tx_id = id(db.session().transaction)
        if tx_id not in self.to_execute:
            self.to_execute[tx_id] = []
        self.to_execute[tx_id].append([func, func_args, func_kwargs])

        logger.info(
            "Registered callback",
            tx_id=tx_id,
            function_name=func.__name__,
        )


manager = OnSuccessfulCommitManager()


def only_on_successful_commit(function):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Wraps a function that should only be executed if the current Session is successfully committed.
    """

    def wrapper(*func_args, **func_kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        manager.register(function, *func_args, **func_kwargs)

    return wrapper
