import flask_login as login
from flask import Blueprint, jsonify, make_response, request
from sqlalchemy.exc import SQLAlchemyError

from audit_log.utils import emit_audit_log_delete, emit_bulk_audit_log_create
from care_advocates.models.assignable_advocates import AssignableAdvocate
from care_advocates.models.matching_rules import MatchingRule, MatchingRuleSet
from care_advocates.schemas.matching_rules import (
    AssignableAdvocateMatchingRuleCreateSchema,
    AssignableAdvocateMatchingRuleSchema,
    AssignableAdvocateMatchingRuleUpdateSchema,
)
from storage.connection import db

URL_PREFIX = "assignable-advocates"

care_advocate_matching = Blueprint(URL_PREFIX, __name__)


class MatchingRuleEndpointMessage(str):
    MISSING_ASSIGNABLE_ADVOCATE = "no assignable_advocate found"
    MISSING_MRS = "no matching rule set found"
    MISSING_FIELDS = "All fields must be filled before saving"
    MRS_DNE = "object not able to be deleted. matching rule set does not exist"
    DELETE_ERROR = "object not able to be deleted"


@care_advocate_matching.route("/<int:id_>/matching-rule-set", methods=["POST"])
@login.login_required
def matching_rule_list(id_):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    schema = AssignableAdvocateMatchingRuleCreateSchema()
    request_json = request.json if request.is_json else None
    validated_input = schema.load(request_json)
    audit_creates = []

    assignable_advocate = AssignableAdvocate.query.get(id_)
    if not assignable_advocate:
        return make_response(
            jsonify(
                {"errors": MatchingRuleEndpointMessage.MISSING_ASSIGNABLE_ADVOCATE}
            ),
            404,
        )

    matching_rules = validated_input["matching_rules"]
    mrs = MatchingRuleSet(assignable_advocate=assignable_advocate)
    db.session.add(mrs)
    audit_creates.append(mrs)

    for matching_rule in matching_rules:
        mr = MatchingRule(**matching_rule, matching_rule_set=mrs)
        db.session.add(mr)
        audit_creates.append(mr)

    db.session.commit()
    emit_bulk_audit_log_create(audit_creates)
    return jsonify(AssignableAdvocateMatchingRuleSchema().dump(mrs))


@care_advocate_matching.route(
    "/<int:advocate_id_>/matching-rule-set/<int:set_id>", methods=["PUT"]
)
@login.login_required
def matching_rule_set(advocate_id_, set_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    schema = AssignableAdvocateMatchingRuleUpdateSchema()
    request_json = request.json if request.is_json else None
    body = schema.load(request_json)

    matching_rule_set = MatchingRuleSet.query.get(set_id)
    if not matching_rule_set:
        return make_response(
            jsonify({"errors": MatchingRuleEndpointMessage.MISSING_MRS}), 404
        )

    matching_rules = body["matching_rules"]

    updated_rules = []
    for rule in matching_rules:
        all_ = rule["all"]
        type_ = rule["type"]
        identifiers = rule["identifiers"]
        entity = rule["entity"]

        is_organization_exclude = entity == "organization" and type_ == "exclude"
        if (len(identifiers) == 0 and not all_) and not is_organization_exclude:
            return make_response(
                jsonify({"errors": MatchingRuleEndpointMessage.MISSING_FIELDS}),
                400,
            )

        updated_rules.append(
            MatchingRule(
                type=type_,
                matching_rule_set_id=matching_rule_set.id,
                entity=entity,
                all=all_,
                identifiers=identifiers,
            )
        )

    matching_rule_set.replace_matching_rules(updated_rules)

    return jsonify(AssignableAdvocateMatchingRuleSchema().dump(matching_rule_set))


@care_advocate_matching.route(
    "/<int:advocate_id_>/matching-rule-set/<int:set_id>", methods=["DELETE"]
)
@login.login_required
def matching_rule_delete(advocate_id_, set_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        mrs = MatchingRuleSet.query.filter(MatchingRuleSet.id == set_id).one()
    except SQLAlchemyError:
        return make_response(
            jsonify({"errors": MatchingRuleEndpointMessage.MRS_DNE}), 400
        )
    try:
        db.session.delete(mrs)
        db.session.commit()
        emit_audit_log_delete(mrs)
    except SQLAlchemyError:
        return make_response(
            jsonify({"errors": MatchingRuleEndpointMessage.DELETE_ERROR}), 400
        )
    return jsonify({"success": True})
