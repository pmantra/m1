from marshmallow import EXCLUDE, Schema, fields


class SelectOrInteger(fields.Integer):
    """SelectOrInteger represents a field that may be one of a set of special values or an integer."""

    def __init__(self, choices):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.choices = choices
        super().__init__()

    def _deserialize(self, value, attr, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value in self.choices:
            return value
        return super()._deserialize(value, attr, data, **kwargs)

    def _serialize(self, value, attr, obj, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value in self.choices:
            return value
        return super()._serialize(value, attr, obj, **kwargs)


class ProgramTransitionSchema(Schema):
    """ProgramTransitionSchema describes a desired change in a user's program content.

    Attributes:
        source_name: The name of any configured track
        destination_name: The name of any configured track
        action_name: A transition command:
            "commit-transition" for finalizing an ongoing transition
            "cancel-transition" for backing out of an ongoing transition

        source: Integer representing a care program id.
        destination: May be an integer representing a module id,
            "commit-transition" for finalizing an ongoing program transition,
            "cancel-transition" for backing out of an ongoing transition.
    """

    source_name = fields.String()
    destination_name = fields.String()
    action_name = fields.String()

    # TODO: [Tracks] Remove below eventually
    source = fields.Integer()
    destination = SelectOrInteger(choices={"commit-transition", "cancel-transition"})

    class Meta:
        unknown = EXCLUDE


class _TransitionDescriptionSchema(Schema):
    description = fields.String()
    subject = fields.Nested(ProgramTransitionSchema)


class ProgramTransitionsSchema(Schema):
    my_program_display_name = fields.String()
    transitions = fields.Nested(_TransitionDescriptionSchema, many=True)
