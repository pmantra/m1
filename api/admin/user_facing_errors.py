from __future__ import annotations

import html
from collections.abc import Callable
from typing import Any

from flask import url_for
from werkzeug.routing import BuildError

import cost_breakdown.errors as errors
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from utils.log import logger
from wallet.models.reimbursement import ReimbursementRequest

log = logger(__name__)


class ErrorMessageImprover:
    """
    Returns custom error messages for Admin's Cost Breakdown Calculator with actionable context.
    """

    default_message = (
        "An unexpected error has occurred. "
        "Please reach out to @payments-platform-oncall and provide the following message: {message}"
    )

    def __init__(
        self, procedure: TreatmentProcedure | ReimbursementRequest | str = "procedure"
    ):
        self.procedure = procedure
        self.messages: dict[Any, Callable | str] = self._init_messages()

    def __repr__(self) -> str:
        return f"<ErrorMessageImprover | {self.procedure}>"

    def _init_messages(self) -> dict[Any, Callable | str]:
        """
        List of error messages that depend on the procedure type.
        """
        return {
            errors.NoCostSharingCategory: lambda: "{procedure} is missing a Global Procedure Id."
            if isinstance(self.procedure, TreatmentProcedure)
            else "{procedure} is missing a Cost Sharing Category"
            if isinstance(self.procedure, ReimbursementRequest)
            else None
        }

    def get_error_message(self, error: Exception, formatter: Callable = str) -> str:
        """
        Find the custom error message corresponding to the given exception.
        Format the error message for display in admin (ex: with links) or otherwise.
        """
        if error.__class__ in self.messages:
            message = self.messages[error.__class__]
            if callable(message):
                message = message()
                if isinstance(message, str):
                    return message.format(procedure=formatter(self.procedure))
        elif isinstance(error, errors.ImprovableException):
            message = error.get_internal_message()
            kwargs = {
                keyword: formatter(argument)
                for keyword, argument in error.get_format_kwargs().items()
            }
            return str(message).format(procedure=formatter(self.procedure), **kwargs)
        elif isinstance(error, errors.ActionableCostBreakdownException) or isinstance(
            error, errors.CostBreakdownCalculatorValidationError
        ):
            return str(error)

        # if a conditional error message hits an unexpected case
        log.error(
            "Unexpected Error Message Situation for the Cost Breakdown Calculator",
            original_error=error,
            error_params=self,
        )
        return self.default_message.format(message=str(error))

    @staticmethod
    def format_as_admin_url(model_obj: Any) -> str:
        """
        Get an associated admin page for the model_obj via the flask url_for function.
        This takes advantage of our view names drawing from the sqlalchemy model by default.
        In non-default cases, additional logic will be necessary.
        This value is inserted into the inner_html of the calculator error alert.
        """
        if isinstance(model_obj, str):
            return model_obj
        try:
            view_name = model_obj.__class__.__name__.lower()
            url = url_for(f"{view_name}.edit_view", id=model_obj.id)
            return f"<a href='{url}'>{html.escape(str(model_obj))}</a>"
        except BuildError:
            log.error(
                "Unable to format a custom error for the Cost Breakdown Calculator: No associated admin page found",
                unassociated_object=model_obj,
            )
            return str(model_obj)
