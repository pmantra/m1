import enum
import json
import os
import re
import time
from abc import abstractmethod
from typing import Any, Callable, Iterable, Tuple, Type, TypeVar

import flask_login as login
from dateutil.parser import parse
from flask import flash, request
from flask_admin import expose
from flask_admin.actions import action
from flask_admin.contrib.sqla import ModelView
from flask_admin.contrib.sqla.filters import BaseSQLAFilter
from flask_admin.contrib.sqla.form import InlineModelConverter, get_form
from flask_admin.contrib.sqla.tools import get_primary_key
from flask_admin.form import FormOpts, rules
from flask_admin.menu import MenuLink
from flask_admin.model import InlineFormAdmin
from flask_admin.model.fields import InlineFieldList, InlineModelFormField
from sqlalchemy.orm import class_mapper
from werkzeug.utils import redirect
from wtforms import FormField, Label, fields, form, widgets

from admin.views.auth import AdminAuth
from audit_log.utils import ActionType, emit_audit_log_line, get_modified_field_value
from common.constants import Environment
from storage.connection import RoutingSQLAlchemy, db
from utils.log import logger
from utils.payments import convert_cents_to_dollars, convert_dollars_to_cents

log = logger(__name__)


class AdminCategory(str, enum.Enum):
    ADMIN = "Admin"
    AUTHN = "Authentication"
    AUTHZ = "Authz"
    BOOKINGS = "Bookings"
    CONTENT = "Content"
    DASH = "Dashboard"
    DEV = "Developer"
    ENTERPRISE = "Enterprise"
    FORUM = "Forum"
    PAY = "Payments"
    PRACTITIONER = "Practitioners"
    USER = "User"
    WALLET = "Wallet"
    WALLET_CONFIG = "Wallet Config"
    WALLET_REPORTING = "Wallet Reporting"

    def __str__(self) -> str:
        return self.value


AdminViewT = TypeVar("AdminViewT")
ViewsFactoryT = Callable[[], Tuple[AdminViewT, ...]]
LinkFactoryT = Callable[[], Tuple["AuthenticatedMenuLink", ...]]


class ContainsFilter(BaseSQLAFilter):
    def operation(self) -> str:
        return "contains"


class IsFilter(BaseSQLAFilter):
    def operation(self) -> str:
        return "is"


class BaseDateTextFilter(BaseSQLAFilter):
    def operation(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        pass

    def __init__(self, name, options=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(name, options, data_type="text")

    def validate(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            self.clean(value)
            return True
        except (ValueError, TypeError) as e:
            flash(str(e), category="error")
            return False

    def clean(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return parse(value)


class InlineCollectionView:
    """InlineCollectionView allows a view to manage a non-model collection using inline form lists."""

    parent_attribute = None
    child_pk = None

    field_list_args = {}
    form_field_args = {}

    def get_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        raise NotImplementedError(
            "Please return a form class representing the individual collection member."
        )

    def get_collection(self, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        raise NotImplementedError(
            "Please return the collection in terms of the parent model instance."
        )

    def set_collection(self, model, data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        raise NotImplementedError(
            "Please persist the collection as mutated by the client."
        )

    def contribute(self, _model, form_class):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        view = self

        class CustomFormList(InlineFieldList):
            def populate_obj(self, model, _name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
                collection = [
                    {"data": f.data, "should_delete": self.should_delete(f)}
                    for f in self.entries
                ]
                view.set_collection(model, collection)

        child_form = self.get_form()
        form_field = InlineModelFormField(
            child_form, self.child_pk, **self.form_field_args
        )
        field_list = CustomFormList(form_field, **self.field_list_args)
        setattr(form_class, self.parent_attribute, field_list)  # type: ignore[arg-type] # Argument 2 to "setattr" has incompatible type "None"; expected "str"
        return form_class


class CustomInlineConverter(InlineModelConverter):
    def contribute(self, model, form_class, inline_model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(inline_model, InlineCollectionView):
            return inline_model.contribute(model, form_class)
        else:
            return super().contribute(model, form_class, inline_model)


class SimpleSortViewMixin:
    simple_sorters = {}
    """
    Provide a dictionary of {'column_name': sorting_func or None} for sorting
    on properties that cannot be sorted in the database (dynamic properties,
    json properties, etc...). If no sorting func is provided the function will
    simply be: lambda x: getattr(x, 'column_name')

    WARNING: Do NOT use this on model views with large datasets! It relies on
    loading the entire query result in memory and calling the sort function
    for each model instance.
    """

    def __init__(self, model, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._simple_sort_column = None
        self._sort_desc = None
        super().__init__(model, *args, **kwargs)  # type: ignore[call-arg] # Too many arguments for "__init__" of "object"

    def get_sortable_columns(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return {
            **super().get_sortable_columns(),
            **{x: None for x in self.simple_sorters.keys()},
        }

    def get_list(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        page,
        sort_column,
        sort_desc,
        search,
        filters,
        execute=True,
        page_size=None,
    ):
        self._sort_desc = sort_desc
        execute = False if sort_column in self.simple_sorters.keys() else execute
        return super().get_list(
            page, sort_column, sort_desc, search, filters, execute, page_size
        )

    def _apply_sorting(self, query, joins, sort_column, sort_desc):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if sort_column in self.simple_sorters.keys():
            self._simple_sort_column = sort_column
            return query, joins
        return super()._apply_sorting(query, joins, sort_column, sort_desc)

    def _apply_pagination(self, query, page, page_size):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self._simple_sort_column is not None:
            sorted_result = sorted(
                query,
                key=self.simple_sorters[self._simple_sort_column]  # type: ignore[arg-type] # Argument "key" to "sorted" has incompatible type "Union[Any, Callable[[Any], Any]]"; expected "None"
                or (lambda x: getattr(x, self._simple_sort_column)),
                reverse=self._sort_desc,  # type: ignore[arg-type] # Argument "reverse" to "sorted" has incompatible type "Optional[Any]"; expected "bool"
            )
            self._simple_sort_column = None
            offset = page * (page_size or self.page_size)  # type: ignore[attr-defined] # "SimpleSortViewMixin" has no attribute "page_size"
            return sorted_result[offset : (page_size or self.page_size) + offset]  # type: ignore[attr-defined] # "SimpleSortViewMixin" has no attribute "page_size"
        return super()._apply_pagination(query, page, page_size)


class BulkUpdateForm(form.Form):
    ids = fields.HiddenField()
    action_name = fields.HiddenField()

    def take_action(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        raise NotImplementedError()


class ModalUpdateMixin:
    """
    Mixin class to add bulk modal update functionality to the list view.
    Define BulkUpdateForms for your actions, update modal_change_forms with
    action_name -> form_class.
    """

    list_template = "modal_update_list_template.html"

    modal_change_forms = {}

    def init_actions(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        for action_name in self.modal_change_forms.keys():

            @action(action_name, " ".join(action_name.split("_")).title())
            def modal_action(_):  # type: ignore[no-untyped-def] # Function is missing a type annotation
                url = self.get_url(".index_view")  # type: ignore[attr-defined] # "ModalUpdateMixin" has no attribute "get_url"
                return redirect(url, code=307)

            setattr(self, f"action_{action_name}", modal_action)
        super().init_actions()

    @expose("/", methods=["POST"])
    def index(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        url = self.get_url(".index_view")  # type: ignore[attr-defined] # "ModalUpdateMixin" has no attribute "get_url"
        ids = request.form.getlist("rowid")
        action_name = request.form["action"]
        change_form = self.modal_change_forms[action_name]()
        change_form.ids.data = ",".join(ids)
        change_form.action_name.data = action_name

        self._template_args["url"] = url  # type: ignore[attr-defined] # "ModalUpdateMixin" has no attribute "_template_args"
        self._template_args["change_form"] = change_form  # type: ignore[attr-defined] # "ModalUpdateMixin" has no attribute "_template_args"
        self._template_args["change_modal"] = True  # type: ignore[attr-defined] # "ModalUpdateMixin" has no attribute "_template_args"
        return self.index_view()  # type: ignore[attr-defined] # "ModalUpdateMixin" has no attribute "index_view"

    @expose("/update/", methods=["POST"])
    def update_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        url = self.get_url(".index_view")  # type: ignore[attr-defined] # "ModalUpdateMixin" has no attribute "get_url"
        change_form = self.modal_change_forms[request.form["action_name"]](request.form)
        if change_form.validate():
            change_form.take_action()
            return redirect(url)
        else:
            self._template_args["url"] = url  # type: ignore[attr-defined] # "ModalUpdateMixin" has no attribute "_template_args"
            self._template_args["change_form"] = change_form  # type: ignore[attr-defined] # "ModalUpdateMixin" has no attribute "_template_args"
            self._template_args["change_modal"] = True  # type: ignore[attr-defined] # "ModalUpdateMixin" has no attribute "_template_args"
            return self.index_view()  # type: ignore[attr-defined] # "ModalUpdateMixin" has no attribute "index_view"


class FormToJSONField(fields.FormField):
    def __init__(self, field_dict, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        form_class = type(
            "_JSONFieldsForm",
            (form.Form,),
            {k: fields.StringField(k, default=v) for k, v in field_dict.items()},
        )
        super().__init__(form_class, *args, **kwargs)

    def populate_obj(self, obj, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        setattr(obj, name, self.form.data)


class ForwardInlineModelForm(InlineModelFormField):
    """
    From: https://gist.github.com/DrecDroid/398a05e4945805bc09d1
    """

    def __init__(self, form, session, model, inline_view, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Default constructor.
        :param form:
            Form for the related model
        :param session:
            SQLAlchemy session
        :param model:
            Related model
        :param inline_view:
            Inline view
        """
        self.form = form
        self.session = session
        self.model = model
        self.inline_view = inline_view

        self._pk = get_primary_key(model)

        # Generate inline form field
        form_opts = FormOpts(
            widget_args=getattr(inline_view, "form_widget_args", None),
            form_rules=inline_view._form_rules,
        )

        super().__init__(form, self._pk, form_opts=form_opts, **kwargs)

    def populate_obj(self, obj, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        value = getattr(obj, name, None)
        inline_form = self.form

        if value:
            model = value
        else:
            model = self.model()
            setattr(obj, name, model)

        for name, field in self.form._fields.items():
            if name != self._pk:
                field.populate_obj(model, name)

        self.inline_view.on_model_change(inline_form, model, model.id is None)


class ForwardInlineModelConverter(InlineModelConverter):
    """
    From: https://gist.github.com/DrecDroid/398a05e4945805bc09d1
    """

    inline_field_list_type = ForwardInlineModelForm

    def contribute(self, model, form_class, inline_model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        mapper = model._sa_class_manager.mapper
        info = self.get_info(inline_model)

        # Find property from target model to current model
        target_mapper = info.model._sa_class_manager.mapper

        for prop in mapper.iterate_properties:
            if hasattr(prop, "direction") and prop.direction.name == "MANYTOONE":
                if prop.mapper.class_ == target_mapper.class_:
                    forward_prop = prop
                    break
        else:
            raise Exception(f"Cannot find forward relation for model {info.model}")

        for prop in target_mapper.iterate_properties:
            if hasattr(prop, "direction") and prop.direction.name == "ONETOMANY":
                if prop.mapper.class_ == mapper.class_:
                    reverse_prop = prop
                    break
        else:
            raise Exception(f"Cannot find reverse relation for model {info.model}")

        # Remove reverse property from the list
        ignore = [reverse_prop.key]

        if info.form_excluded_columns:
            exclude = ignore + list(info.form_excluded_columns)
        else:
            exclude = ignore

        # Create converter
        converter = self.model_converter(self.session, info)

        # Create form
        child_form = info.get_form()

        if child_form is None:
            child_form = get_form(
                info.model,
                converter,
                only=info.form_columns,
                exclude=exclude,
                field_args=info.form_args,
                hidden_pk=True,
            )

        # Post-process form
        child_form = info.postprocess_form(child_form)

        kwargs = {}

        label = self.get_label(info, forward_prop.key)
        if label:
            kwargs["label"] = label

        if self.view.form_args:
            field_args = self.view.form_args.get(forward_prop.key, {})
            kwargs.update(**field_args)

        setattr(
            form_class,
            forward_prop.key,
            self.inline_field_list_type(
                child_form, self.session, info.model, info, **kwargs
            ),
        )

        return form_class


class ManyToOneInlineForm(InlineFormAdmin):
    inline_converter = ForwardInlineModelConverter


class PerInlineModelConverterMixin:
    """
    From: https://gist.github.com/DrecDroid/398a05e4945805bc09d1
    """

    def scaffold_inline_form_models(self, form_class):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        inline_converter = self.inline_model_form_converter(  # type: ignore[attr-defined] # "PerInlineModelConverterMixin" has no attribute "inline_model_form_converter"
            self.session, self, self.model_form_converter  # type: ignore[attr-defined] # "PerInlineModelConverterMixin" has no attribute "session" #type: ignore[attr-defined] # "PerInlineModelConverterMixin" has no attribute "model_form_converter"
        )

        for m in self.inline_models:  # type: ignore[attr-defined] # "PerInlineModelConverterMixin" has no attribute "inline_models"
            if hasattr(m, "inline_converter"):
                custom_converter = m.inline_converter(
                    self.session, self, self.model_form_converter  # type: ignore[attr-defined] # "PerInlineModelConverterMixin" has no attribute "session" #type: ignore[attr-defined] # "PerInlineModelConverterMixin" has no attribute "model_form_converter"
                )
                form_class = custom_converter.contribute(self.model, form_class, m)  # type: ignore[attr-defined] # "PerInlineModelConverterMixin" has no attribute "model"
            else:
                form_class = inline_converter.contribute(self.model, form_class, m)  # type: ignore[attr-defined] # "PerInlineModelConverterMixin" has no attribute "model"

        return form_class


class DictToJSONField(fields.TextAreaField):
    def process_data(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value is None:
            value = {}

        self.data = json.dumps(value)

    def process_formdata(self, valuelist):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # it saves the last non-empty value when the form field is empty.
        log.debug("DictToJSONField process_formdata(valuelist=%s)", valuelist)
        if valuelist and valuelist[0]:
            self.data = json.loads(valuelist[0])
        else:
            self.data = {}  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[Never, Never]", variable has type "str")


_DECIMAL_PART_RE = r"[0-9]*(\.[0-9]{1,2})?"
DOLLAR_RE = r"^" + _DECIMAL_PART_RE + r"$"
ALLOW_NEGATIVE_DOLLAR_RE = r"^-?" + _DECIMAL_PART_RE + r"$"


class CustomFormField(FormField):
    def populate_obj(self, obj: Any, name: str) -> None:
        pass


class AmountDisplayCentsInDollarsField(fields.DecimalField):
    widget = widgets.NumberInput(step=0.01, min=0)

    def __init__(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        label=None,
        validators=None,
        places=2,
        rounding=None,
        allow_negative=False,
        **kwargs,
    ):
        super().__init__(
            label=label,
            validators=validators,
            places=places,
            rounding=rounding,
            render_kw={"placeholder": "0.00"},
            **kwargs,
        )

        if allow_negative:
            self.widget.min = None
            dollar_re = ALLOW_NEGATIVE_DOLLAR_RE
        else:
            dollar_re = DOLLAR_RE

        self.compiled_re = re.compile(dollar_re)

    def process_data(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value:
            value = convert_cents_to_dollars(value)
        return super().process_data(value)

    def process_formdata(self, valuelist):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # DecimalField only reads the first value, so this is okay
        if valuelist and valuelist[0] and not self.compiled_re.match(valuelist[0]):
            raise ValueError("Not a valid dollar value (###.##)")
        return super().process_formdata(valuelist)

    def populate_obj(self, obj, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # parent reads from self.data, which we want to keep in dollars, so no parent call
        data = None
        if self.data is not None:
            data = convert_dollars_to_cents(self.data)
        setattr(obj, name, data)


def cents_to_dollars_formatter(view, context, model, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    value = getattr(model, name)
    return f"${convert_cents_to_dollars(value):.2f}" if value is not None else ""


class ViewExtras:
    app_start_time = int(time.time())
    # The env variables listed in public_client_side_env will have their values
    # injected into the Admin frontend and will be viewable by users.
    # Only for use with non-sensitive values needed by frontend code.
    public_client_side_env = []
    env_vars_injected = False

    @property
    def extra_js(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation

        base = os.path.dirname(os.path.realpath(__file__))
        env_file = "/static/js/env.js"

        if not ViewExtras.env_vars_injected:
            client_env_dict = {}
            # special case for this one env var, as we're using the enum constant mapping rather than directly
            # using the raw ENVIRONMENT env var
            client_env_dict["ENVIRONMENT"] = Environment.current().name

            for env_var_info in ViewExtras.public_client_side_env:
                client_env_dict[env_var_info["key"]] = os.environ.get(
                    env_var_info["key"], env_var_info["default"]
                )
            with open(os.path.join(base, f"..{env_file}"), "w") as file:
                file.write(f"window.envJSON = '{json.dumps(client_env_dict)}';")
            ViewExtras.env_vars_injected = True

        main_js_bundle = "/static/js/app-min-v2.js"
        timestamp = self.app_start_time

        if os.path.exists(os.path.join(base, "../static/js-dev/app-dev.js")):
            main_js_bundle = "/static/js-dev/app-dev.js"
            timestamp = int(time.time())

        return [f"{env_file}?{timestamp}", f"{main_js_bundle}?{timestamp}"]

    @property
    def extra_css(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return [f"/static/css/overrides.css?{self.app_start_time}"]


class MavenAdminView(AdminAuth, ModelView, ViewExtras):
    inline_model_form_converter = CustomInlineConverter
    can_set_page_size = True

    list_template = "list.html"

    def __init__(self, model, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(model, *args, **kwargs)

        # Use column / relationship doc values as the default form field title.
        for c in class_mapper(model).iterate_properties:
            if hasattr(c, "doc") and c.doc:
                self.form_widget_args.setdefault(c.key, {}).setdefault("title", c.doc)

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form, id)
        model = super().get_one(id)
        if model is None:
            return

        if self.inline_models:
            for m in self.inline_models:
                if isinstance(m, InlineCollectionView):
                    getattr(form, m.parent_attribute).process(  # type: ignore[call-overload] # No overload variant of "getattr" matches argument types "Any", "None"
                        None, data=m.get_collection(model)
                    )

    @classmethod
    @abstractmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        """Factory method for initializing a view."""


class AdminAuditLogMixin(MavenAdminView):
    audit_model_view = None
    inline_to_create = set()

    def _get_inline_model(self, inline_model_data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Inline model. Can be one of
         - ``tuple``, first value is related model instance,
         second is dictionary with options
         - ``InlineFormAdmin`` instance
         - Model class
        """
        if hasattr(inline_model_data, "_sa_class_manager"):
            model = inline_model_data
        else:
            model = getattr(inline_model_data, "model", None)
        return model

    def _get_inline_model_field(self, inline_model, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        target_mapper = inline_model._sa_class_manager.mapper.base_mapper
        for prop in target_mapper.iterate_properties:
            if hasattr(prop, "direction") and prop.direction.name in (
                "MANYTOONE",
                "MANYTOMANY",
            ):
                reverse_prop = prop
                if reverse_prop.direction.name == "MANYTOONE":
                    candidate = "ONETOMANY"
                else:
                    candidate = "MANYTOMANY"

                for new_prop in model._sa_class_manager.mapper.iterate_properties:
                    if (
                        hasattr(new_prop, "direction")
                        and new_prop.direction.name == candidate
                    ):
                        return new_prop.key

    def _get_inline_data(self, model, inline_model_data) -> Iterable:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        inline_model = self._get_inline_model(inline_model_data)
        if not inline_model:
            log.debug(
                "No data model found for inline data type. Will not audit log.",
                inline_data_type=inline_model_data,
            )
            return []
        inline_model_field = self._get_inline_model_field(inline_model, model)
        if not inline_model_field:
            log.debug(
                "No sqlalchemy relationship found for inline data type. Will not audit log.",
                inline_data_type=inline_model_data,
            )
            return []
        data = get_modified_field_value(model, inline_model_field)
        return data

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_model_change(form, model, is_created)

        if self.inline_models:
            # Inline models may be created on any update, not just is_created updates
            for inline_model_data in self.inline_models:
                data = self._get_inline_data(model, inline_model_data)
                for inline_data in data:
                    if inline_data in db.session.deleted:
                        emit_audit_log_line(
                            login.current_user,
                            ActionType.DELETE,
                            inline_data,
                            is_inline=True,
                        )
                    else:
                        instance_state = db.inspect(inline_data)
                        if instance_state.pending:
                            # setting up a hack comparing before and after the commit to find inline create events
                            # can't commit here because there will be no id
                            self.inline_to_create.add(inline_data)
                        else:
                            emit_audit_log_line(
                                login.current_user,
                                ActionType.UPDATE,
                                inline_data,
                                is_inline=True,
                            )

        # only log on updates because we need id for creates -- see after_model_change for creates
        if is_created:
            return

        log.debug("Will emit audit log, triggered by on_model_change")
        emit_audit_log_line(
            login.current_user,
            ActionType.UPDATE,
            model,
        )

    def after_model_change(self, form, model, is_created):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().after_model_change(form, model, is_created)

        if self.inline_models:
            # Inline models may be created on any update, not just is_created updates
            for inline_model_data in self.inline_models:
                data = self._get_inline_data(model, inline_model_data)
                for inline_data in data:
                    if inline_data in self.inline_to_create:
                        emit_audit_log_line(
                            login.current_user,
                            ActionType.CREATE,
                            inline_data,
                            is_inline=True,
                        )

        # only log on creates -- see on_model_change for updates
        if not is_created:
            return

        log.debug("Will emit audit log, triggered by after_model_change")
        emit_audit_log_line(
            login.current_user,
            ActionType.CREATE,
            model,
        )

    def on_model_delete(self, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_model_delete(model)

        log.debug("Will emit audit log, triggered by on_model_delete")
        emit_audit_log_line(
            login.current_user,
            ActionType.DELETE,
            model,
        )

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form, id)
        model = self.get_one(id)
        if model is None:
            return

        log.debug("Will emit audit log, triggered by on_form_prefill")

        emit_audit_log_line(
            login.current_user,
            ActionType.READ,
            model,
        )

    def get_one(self, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        model = super().get_one(id)
        if model is None:
            return

        log.debug("Will emit audit log, triggered by get_one")
        current_user = login.current_user
        if current_user:
            emit_audit_log_line(
                current_user,
                ActionType.READ,
                model,
            )
        return model


class MavenAuditedView(AdminAuditLogMixin):
    audit_model_view = None


class AuthenticatedMenuLink(AdminAuth, MenuLink):
    pass


USER_AJAX_REF = {
    "fields": ("first_name", "last_name", "username", "email", "id"),
    "page_size": 10,
}


class ReadOnlyFieldRule(rules.Macro):
    """
    A form rule for rendering a static field with no form input.

    There's some pretty hacky code in here, but it's necessary so that the readonly field
    gets rendered with a label just like other form items.

    Usage:
        form_edit_rules = (
            "normal_field_here",
            ...,
            ReadOnlyFieldRule("The Label", lambda model: model.some_attribute_getter()),
            ReadOnlyFieldRule("Another Label", lambda _, form: something_fancy(form))
        )
    """

    class Field:
        def __init__(self, name, value, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            self.label = Label("", name)
            self.value = value
            self.validators = []

        def __call__(self, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            return f'<div style="padding-top: 5px">{self.value}</div>'

    def __init__(self, name, getter, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.getter = getter
        self.name = name
        super().__init__("lib.render_field", **kwargs)

    def __call__(self, form, form_opts=None, field_args=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        import inspect

        # If getter takes 1 argument, pass only model
        # Otherwise pass model and form
        if field_args is None:
            field_args = {}
        arity = len(inspect.getfullargspec(self.getter).args)
        args = [form._obj]
        if arity and arity > 1:
            args.append(form)
        value = self.getter(*args)
        field = ReadOnlyFieldRule.Field(self.name, value)
        params = {"form": form, "field": field, "kwargs": {}}
        return super().__call__(form, form_opts, params)
