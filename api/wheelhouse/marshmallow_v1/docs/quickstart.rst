.. _quickstart:
.. module:: marshmallow

Quickstart
==========

This guide will walk you through the basics of creating schemas for serializing and deserializing data.

Declaring Schemas
-----------------

Let's start with a basic user "model".

.. code-block:: python

    import datetime as dt

    class User(object):
        def __init__(self, name, email, age=None):
            self.name = name
            self.email = email
            self.created_at = dt.datetime.now()
            self.friends = []
            self.employer = None
            self.age = age

        def __repr__(self):
            return '<User(name={self.name!r})>'.format(self=self)


Create a schema by defining a class with variables mapping attribute names to :class:`Field <fields.Field>` objects.

.. code-block:: python

    from marshmallow import Schema, fields, pprint

    class UserSchema(Schema):
        name = fields.String()
        email = fields.Email()
        created_at = fields.DateTime()

.. seealso::

    For a full reference on the available field classes, see the :ref:`API Docs <api_fields>`.


Serializing Objects
-------------------

Serialize objects by passing them to your schema's :meth:`dump <marshmallow.Schema.dump>` method, which returns the formatted result (as well as a dictionary of validation errors, which we'll :ref:`revisit later <validation>`).

.. code-block:: python

    user = User(name="Monty", email="monty@python.org")
    schema = UserSchema()
    result = schema.dump(user)
    pprint(result.data)
    # {"name": "Monty",
    #  "email": "monty@python.org",
    #  "created_at": "2014-08-17T14:54:16.049594+00:00"}

You can also serialize to a JSON-encoded string using :meth:`dumps <marshmallow.Schema.dumps>`.

.. code-block:: python

    json_result = schema.dumps(user)
    pprint(json_result.data)
    # '{"name": "Monty", "email": "monty@python.org", "created_at": "2014-08-17T14:54:16.049594+00:00"}'

Filtering output
++++++++++++++++

You may not need to output all declared fields every time you use a schema. You can specify which fields to output with the ``only`` parameter.

.. code-block:: python

    summary_schema = UserSchema(only=('name', 'email'))
    summary_schema.dump(user).data
    # {"name": "Monty Python", "email": "monty@python.org"}

You can also exclude fields by passing in the ``exclude`` parameter.


Deserializing Objects
---------------------

The opposite of the :meth:`dump <Schema.dump>` method is the :meth:`load <Schema.load>` method, which deserializes an input dictionary to an application-level data structure.

By default, :meth:`load <Schema.load>` will return a dictionary of field names mapped to the deserialized values.

.. code-block:: python

    from pprint import pprint

    user_data = {
        'created_at': '2014-08-11T05:26:03.869245',
        'email': u'ken@yahoo.com',
        'name': u'Ken'
    }
    schema = UserSchema()
    result = schema.load(user_data)
    pprint(result.data)
    # {'name': 'Ken',
    #  'email': 'ken@yahoo.com',
    #  'created_at': datetime.datetime(2014, 8, 11, 5, 26, 3, 869245)},

Notice that the datetime string was converted to a `datetime` object.

Deserializing to Objects
++++++++++++++++++++++++

In order to deserialize to an object, define the :meth:`make_object <Schema.make_object>` method of your :class:`Schema`. The method receives a dictionary of deserialized data as its only parameter.

.. code-block:: python
    :emphasize-lines: 8,9

    # Same as above, but this time we define ``make_object``
    class UserSchema(Schema):

        name = fields.String()
        email = fields.Email()
        created_at = fields.DateTime()

        def make_object(self, data):
            return User(**data)

Now, the :meth:`load <Schema.load>` method will return a ``User`` object.

.. code-block:: python

    user_data = {
        'name': 'Ronnie',
        'email': 'ronnie@stones.com'
    }
    schema = UserSchema()
    result = schema.load(user_data)
    result.data  # => <User(name='Ronnie')>

Handling Collections of Objects
-------------------------------

Iterable collections of objects are also serializable and deserializable. Just set ``many=True``.

.. code-block:: python
    :emphasize-lines: 3,4

    user1 = User(name="Mick", email="mick@stones.com")
    user2 = User(name="Keith", email="keith@stones.com")
    users = [user1, user2]
    schema = UserSchema(many=True)
    result = schema.dump(users)  # OR UserSchema().dump(users, many=True)
    result.data
    # [{'name': u'Mick',
    #   'email': u'mick@stones.com',
    #   'created_at': '2014-08-17T14:58:57.600623+00:00'}
    #  {'name': u'Keith',
    #   'email': u'keith@stones.com',
    #   'created_at': '2014-08-17T14:58:57.600623+00:00'}]


.. _validation:

Validation
----------

:meth:`Schema.load` (and its JSON-decoding counterpart, :meth:`Schema.loads`) returns a dictionary of validation errors as the second element of its return value. Some fields, such as the :class:`Email <fields.Email>` and :class:`URL <fields.URL>` fields, have built-in validation.

.. code-block:: python

    data, errors = UserSchema().load({'email': 'foo'})
    errors  # => {'email': ['foo is not a valid email address.']}
    # OR, equivalently
    result = UserSchema().load({'email': 'foo'})
    result.errors  # => {'email': ['foo is not a valid email address.']}


You can perform additional validation for a field by passing it a ``validate`` callable (function, lambda, or object with ``__call__`` defined).

.. code-block:: python
    :emphasize-lines: 2

    class ValidatedUserSchema(UserSchema):
        age = fields.Number(validate=lambda n: 18 <= n <= 40)

    in_data = {'name': 'Mick', 'email': 'mick@stones.com', 'age': 71}
    result = ValidatedUserSchema().load(in_data)
    result.errors  # => {'age': ['Validator <lambda>(71.0) is False']}


Validation functions either return a boolean or raise a :exc:`ValidationError`. If a :exc:`ValidationError` is raised, its message is stored when validation fails.

.. code-block:: python

    from marshmallow import Schema, fields, ValidationError

    def validate_quantity(n):
        if n < 0:
            raise ValidationError('Quantity must be greater than 0.')
        if n > 30:
            raise ValidationError('Quantity must not be greater than 30.')

    class ItemSchema(Schema):
        quantity = fields.Integer(validate=validate_quantity)

    in_data = {'quantity': 31}
    result, errors = ItemSchema().load(in_data)
    errors  # => {'quantity': ['Quantity must not be greater than 30.']}

.. note::

    If you have multiple validations to perform, you may also pass a collection (list, tuple) or generator of callables to the ``validate`` parameter.

.. note::

    :meth:`Schema.dump` also validates the format of its fields and returns a dictionary of errors. However, the callables passed to ``validate`` are only applied during deserialization.

.. note::

    If you set ``strict=True`` in either the Schema constructor or as a ``class Meta`` option, an error will be raised when invalid data are passed in.

    .. code-block:: python

        UserSchema(strict=True).load({'email': 'foo'})
        # => UnmarshallingError: "foo" is not a valid email address.


    Alternatively, you can also register a custom error handler function for a schema using the :func:`error_handler <Schema.error_handler>` decorator. See the :ref:`Extending Schemas <extending>` page for more info.


.. seealso::

    Need schema-level validation? See the :ref:`Extending Schemas <schemavalidation>` page.

Required Fields
+++++++++++++++

You can make a field required by passing ``required=True``. An error will be stored if the the value is missing from the input to :meth:`Schema.load`.

.. code-block:: python
    :emphasize-lines: 2,6

    class UserSchema(Schema):
        name = fields.String(required=True)
        email = fields.Email()

    data, errors = UserSchema().load({'email': 'foo@bar.com'})
    errors  # {'name': ['Missing data for required field.']}

Schema.validate
+++++++++++++++

If you only need to validate input data (without deserializing to an object), you can use :meth:`Schema.validate`.

.. code-block:: python

    errors = UserSchema().validate({'name': 'Ronnie', 'email': 'invalid-email'})
    errors  # {'email': ['"invalid-email" is not a valid email address.']}


Specifying Attribute Names
--------------------------

By default, `Schemas` will marshal the object attributes that have the same name as the fields. However, you may want to have different field and attribute names. In this case, you can explicitly specify which attribute names to use.

.. code-block:: python
    :emphasize-lines: 3,4,11,12

    class UserSchema(Schema):
        name = fields.String()
        email_addr = fields.String(attribute="email")
        date_created = fields.DateTime(attribute="created_at")

    user = User('Keith', email='keith@stones.com')
    ser = UserSchema()
    result, errors = ser.dump(user)
    pprint(result)
    # {'name': 'Keith',
    #  'email_addr': 'keith@stones.com',
    #  'date_created': '2014-08-17T14:58:57.600623+00:00'}


.. _meta_options:

Refactoring: Implicit Field Creation
------------------------------------

When your model has many attributes, specifying the field type for every attribute can get repetitive, especially when many of the attributes are already native Python datatypes.

The *class Meta* paradigm allows you to specify which attributes you want to serialize. Marshmallow will choose an appropriate field type based on the attribute's type.

Let's refactor our User schema to be more concise.

.. code-block:: python
    :emphasize-lines: 4,5

    # Refactored schema
    class UserSchema(Schema):
        uppername = fields.Function(lambda obj: obj.name.upper())
        class Meta:
            fields = ("name", "email", "created_at", "uppername")

Note that ``name`` will be automatically formatted as a :class:`String <marshmallow.fields.String>` and ``created_at`` will be formatted as a :class:`DateTime <marshmallow.fields.DateTime>`.

.. note::

    If instead you want to specify which field names to include *in addition* to the explicitly declared fields, you can use the ``additional`` option.

    The schema below is equivalent to above:

    .. code-block:: python

        class UserSchema(Schema):
            uppername = fields.Function(lambda obj: obj.name.upper())
            class Meta:
                additional = ("name", "email", "created_at")  # No need to include 'uppername'

Ordering Output
---------------

For some use cases, it may be useful to maintain field ordering of serialized output. To enable ordering, set the ``ordered`` option to `True`. This will instruct marshmallow to serialize data to a `collections.OrderedDict`.

.. code-block:: python
    :emphasize-lines: 7

    from collections import OrderedDict

    class UserSchema(Schema):
        uppername = fields.Function(lambda obj: obj.name.upper())
        class Meta:
            fields = ("name", "email", "created_at", "uppername")
            ordered = True

    u = User('Charlie', 'charlie@stones.com')
    schema = UserSchema()
    result = schema.dump(u)
    assert isinstance(result.data, OrderedDict)
    # marshmallow's pprint function maintains order
    pprint(result.data, indent=2)
    # {
    #   "name": "Charlie",
    #   "email": "charlie@stones.com",
    #   "created_at": "2014-10-30T08:27:48.515735+00:00",
    #   "uppername": "CHARLIE"
    # }

Next Steps
----------

- Need to represent relationships between objects? See the :ref:`Nesting Schemas <nesting>` page.
- Want to create your own field type? See the :ref:`Custom Fields <custom_fields>` page.
- Need to add schema-level validation, post-processing, or error handling behavior? See the :ref:`Extending Schemas <extending>` page.
- For example applications using marshmallow, check out the :ref:`Examples <examples>` page.
