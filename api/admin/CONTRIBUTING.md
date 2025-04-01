# Maven API Admin - Contributors' Guide
Below you'll find some guidelines for adding or updating features in the
Admin app.

## Third-Party Softwarez
This app is powered by a few third-party libraries. Namely:

- [Flask](https://flask.palletsprojects.com/en/1.1.x/)
- [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/en/2.x/)
- [Flask-Admin](https://flask-admin.readthedocs.io/en/latest/)

Take some time to pull up the docs linked above and understand a bit
about how these libraries interact. You should keep them up for
reference as you go through this documentation and as you contribute to
the source code.

## Blueprints
The `api.admin.blueprints` sub-package is reserved for functionality
that isn't managed by Flask-Admin. The modules are organized by
url-prefix and blueprints are named according to the intended prefix for
the routes underneath.

If a new blueprint is created, be sure to add it to the `URLS` global in
`admin.blueprints.__init__`. This global is used in turn by
`admin.blueprints.register_blueprints`, which is called when the main
application is initialized in `admin.factory.create_app`.


## Model Views
If you've ever worked with Django, these Model Views are meant to mimic
that functionality with Flask-SQLAlchemy models. If you need to
deep-dive on how it all works, you're encouraged to consult the
documentation for Flask-Admin - we've done a little customization to
account for audit trails and authentication, but otherwise these
function as standard Flask-Admin views.

One major feature add is the `factory` classmethod on on Model Views.
This is how we bind our View to the specific Model it should represent.

### Creating a New Model View
When you add a new Model View, the class should be defined in a
module which mirrors the source module. i.e.: `api.models.users.User` ->
`api.admin.views.models.users.UserView`.

### Adding a Model View to the Application
Once the view is defined, you need to add it to the appropriate
category. Each supported category is given its own module within
`api.admin.views`. Within the module is a `get_views` factory function.
You should add your Model View here, calling the `factory` classmethod
with the appropriate configuration (at minimum, the selected category).

### Creating a New Category
Every category receives its own module under `api.admin.views`. This is
no different. There are three steps to adding a category:

1. Add the category name to `api.admin.views.base.AdminCategory`
2. Add the module to `api.admin.views`.
3. Add the `get_views` and `get_links` factory functions.
   - Every module should implement both functions - even if they have no
     links or categories defined.

Once you've created your category, follow the steps above for
creating/adding Model Views.
