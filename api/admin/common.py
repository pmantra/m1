from __future__ import annotations

import base64
import os
import random
import re
import time
import urllib.parse
from gettext import gettext
from typing import Any, Optional, Union

import ddtrace
from flask_admin.contrib.sqla.ajax import QueryAjaxModelLoader

from models import base
from storage.connector import RoutingSQLAlchemy
from tracks import service as tracks_svc

ddtrace.config.trace_headers(
    ["User-Agent", "X-Request-ID", "X-Real-IP", "Device-Model"]
)

ddtrace.patch_all()

from datetime import timedelta

import flask_login as login
from flask import Markup, abort, current_app, request, url_for
from flask_admin._compat import text_type
from flask_admin.form import TimeField
from flask_admin.form import widgets as admin_widgets
from wtforms import fields, validators

from models.verticals_and_specialties import is_cx_vertical_name
from storage.connection import db
from utils.error_reporting import MAVEN_IGNORE_EXCEPTIONS
from utils.exceptions import log_exception
from utils.log import logger

log = logger(__name__)

SPEED_DATING_VERTICALS = (
    "Wellness Coach",
    "Mental Health Provider",
    "Mental Health Specialist",
)


ROOT_URL_PREFIX = "/admin"


def handle_exception(sender, exception, **extra):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info("------- This starts our exception logging ------")
    log.error(exception)
    span = ddtrace.tracer.current_span()
    if span:
        span.set_exc_info(
            type(exception),
            exception,
            exception.__traceback__,
        )

    log.info("Got an exception - disposing DB engine connection pool...")
    for k in [k for k in current_app.config["SQLALCHEMY_BINDS"]] + [None]:
        engine = db.get_engine(current_app, k)
        engine.dispose()
    log.info("DB connections closed!")

    if isinstance(exception, MAVEN_IGNORE_EXCEPTIONS):
        log.debug("Ignorable exception, skip stackdriver reporting.")
        return

    if os.environ.get("TESTING"):
        log.debug("Ignorable from TESTING in environ")
        return

    if current_app.config["DEBUG"]:
        log.debug("Ignoring exception logging while debugging.")
        return

    log_exception(exception, service="admin")
    log.info("------- This ends our exception logging ------")


SLUG_RE = re.compile(r"[A-Za-z0-9-]*$")


def slug_re_check(form, field):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not (isinstance(field.data, str) and SLUG_RE.match(field.data)):
        raise validators.ValidationError(
            f"Slugs should only contain lowercase letters and dashes: {field.data!r}"
        )


SNAKE_CASE_RE = re.compile(r"^[a-z]+([a-z\d]+_|_[a-z\d]+)*[a-z\d]*$")


def snake_case_check(form, field):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not SNAKE_CASE_RE.match(field.data):
        raise validators.ValidationError("Value must be in 'snake_case'")


def strip_textfield(field_to_strip: str) -> Union[str, None]:
    try:
        return field_to_strip.strip()
    except AttributeError:
        return  # type: ignore[return-value] # Return value expected


def https_url(view_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return url_for(
        view_name, _scheme=current_app.config["PREFERRED_URL_SCHEME"], _external=True
    )


def totp_secret(length=16):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    chars = base64._b32alphabet.decode("utf8")  # type: ignore[attr-defined] # Module has no attribute "_b32alphabet"

    return "".join(random.choice(chars) for i in range(length))


def list_routes(application):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    from urllib.parse import unquote

    output = []
    for rule in application.url_map.iter_rules():

        options = {arg: f"[{arg}]" for arg in rule.arguments}

        methods = ",".join(rule.methods)
        url = url_for(rule.endpoint, **options)
        line = unquote(f"{rule.endpoint:50s} {methods:20s} {url}")
        output.append(line)

    for line in sorted(output):
        log.debug(line)


def is_enterprise_cc_appointment(appointment) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    """
    Determine if the appointment is with a care advocate/care coordinator AND
    if the appointment is for an enterprise user
    :param appointment:
    :return: bool
    """
    track_svc = tracks_svc.TrackSelectionService()

    return (
        is_cx_vertical_name(appointment.product.vertical.name)
        and appointment.member
        and track_svc.is_enterprise(user_id=appointment.member.id)
    )


def _get_referer_path():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    referer = urllib.parse.urlparse(request.headers["Referer"])
    return f"{referer.path}{f'?{referer.query}' if referer.query else ''}"


def check_auth():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if not login.current_user.is_authenticated:
        abort(403)


class Select2MultipleField(fields.SelectMultipleField):
    """
    This is a combination of the Select2Field and SelectMultipleField.
    It provides the Select2 styling and functionality of the Select2Field,
    and enables selecting multiple values like the SelectMultipleField.

    There is no extra functionality or customization outside of that.
    If flask-admin or wtforms introduces an equivalent to this, we
    can/should remove this and just use their implementation.

    `Select2 <https://github.com/ivaynberg/select2>`_ styled select widget.

    You must include select2.js, form-x.x.x.js and select2 stylesheet for it to
    work.

    Select2Field
    https://github.com/flask-admin/flask-admin/blob/master/flask_admin/form/fields.py

    SelectMultipleField
    https://github.com/wtforms/wtforms/blob/master/src/wtforms/fields/core.py
    """

    widget = admin_widgets.Select2Widget(multiple=True)

    def __init__(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        label=None,
        validators=None,
        coerce=text_type,
        choices=None,
        allow_blank=False,
        blank_text=None,
        **kwargs,
    ):
        super().__init__(label, validators, coerce, choices, **kwargs)
        self.allow_blank = allow_blank
        self.blank_text = blank_text or " "

    def iter_choices(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not self.choices:
            choices = []
        elif isinstance(self.choices[0], (list, tuple)):
            choices = self.choices
        else:
            choices = zip(self.choices, self.choices)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "zip[Tuple[Any, Any]]", variable has type "List[Any]")

        for value, label in choices:
            selected = self.data is not None and self.coerce(value) in self.data
            yield (value, label, selected)

    def process_data(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            self.data = [self.coerce(v) for v in value]
        except (ValueError, TypeError):
            self.data = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "List[Any]")

    def process_formdata(self, valuelist):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            self.data = [self.coerce(x) for x in valuelist]
        except ValueError:
            raise ValueError(
                self.gettext(
                    "Invalid choice(s): one or more data inputs could not be coerced."
                )
            )


class TimeDeltaField(TimeField):
    """
    This is a time field that converts to a datetime.timedelta instead of a datetime.time
    """

    def process_formdata(self, valuelist):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # implementation mostly from:
        # https://flask-admin.readthedocs.io/en/latest/_modules/flask_admin/form/fields/#TimeField
        if valuelist:
            date_str = " ".join(valuelist)

            if date_str.strip():
                for format in self.formats:
                    try:
                        timetuple = time.strptime(date_str, format)
                        self.data = timedelta(
                            hours=timetuple.tm_hour,
                            minutes=timetuple.tm_min,
                            seconds=timetuple.tm_sec,
                        )
                        return
                    except ValueError:
                        pass

                raise ValueError(gettext("Invalid time format"))
            else:
                self.data = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "timedelta")

    def _value(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.raw_data:
            return " ".join(self.raw_data)
        elif self.data is not None:
            return self.data
        else:
            return ""


def format_column_link(view_name: str, view_id: Optional[int], label: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if view_id is None:
        return view_id
    return Markup(
        f"<a href='{url_for(view_name, id=view_id)}' target='_blank'>{label}</a>"
    )


def format_column_search_link(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    view_name: str, search_label: str, search_param: Optional[Any], label: str
):
    if search_param is None:
        return search_param
    return Markup(
        f"<a href='{url_for(view_name)}?{search_label}={search_param}' target='_blank'>{label}</a>"
    )


class SnowflakeQueryAjaxModelLoader(QueryAjaxModelLoader):
    """
    Works like a normal QueryAjaxModelLoader, but returns ids as strings so they
    don't get truncated by JavaScript's 53-bit integers.
    """

    def format(self, model: base.ModelBase):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not model:
            return None

        pk, label = super().format(model)
        return str(pk), label


class CustomFiltersAjaxModelLoader(SnowflakeQueryAjaxModelLoader):
    """
    Works like a normal SnowflakeQueryAjaxModelLoader, but also can join additional models to the query
    for more complicated filters
    """

    def __init__(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, name: str, session: RoutingSQLAlchemy, model, **options  # type: ignore[no-untyped-def] # Function is missing a type annotation
    ):
        super().__init__(name, session, model, **options)
        self.joins = options.get("joins")

    def get_query(self):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        query = self.session.query(self.model)
        if self.joins:
            query.join(*self.joins)
        return query
