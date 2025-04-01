# Maven API Admin
This is a (psuedo) CMS powered in large part by
[Flask-Admin](https://flask-admin.readthedocs.io/en/latest/).

## How It Works
At a high-level, the Admin app works on top of the API models defined in
`api.models`. Flask-Admin works by defining a View model which is
associated to a Flask-SQLAlchemy model. Each of these view models is
then registered under a master blueprint which is then attached to the
app.

## Code Structure:
The Code is organized as follows:

    api/admin/
    ... app.py      <--- WSGI interface
    ... common.py   <--- Shared utilities and globals
    ... factory.py  <--- Application factory
    ... login.py    <--- Login utilities
    ... blueprints/ <--- Custom blueprints not managed by Flask-Admin
        __init__.py     <--- Global `URLS` accessor
        ...             <--- Every blueprint has its own module
    ... views/      <--- Views managed by Flask-Admin
        ... models/
            ...             <--- Model Views, mirroring `api.models` structure
        ...             <--- Model Views and Links, organized by category

### Motivations
The code has been organized in a way which limits dependency leakage
between layers. As such, the higher the layer, the more minimal the
visual code:

- `app.py` knows only about `factory::create_app`
- `factory.py` knows only about `blueprints::register_blueprints`,
  `views::init_admin`, and the few other third-party plugins we use.

This allows us to update units of code without fundamentally altering
others. It aids collaboration by (1) making each layer a single,
digestible piece; and (2) cleaning up the git log so that history is
only reflected against code with meaningful changes.

### Session Management
As part of our security measures to minimize exposure and risk to PII
and PHI, we timeout admin sessions at 10 minutes of inactivity.
Inactivity is defined as no new requests to the server for that session.

Sessions are determined by flask's `PERMANENT_SESSION_LIFETIME` variable.
By default, this has a value of 31 days. In `configuration.py`, we
configure the flask admin app to look for an environment variable
matching `PERMANENT_SESSION_LIFETIME`.

Our environment variables
are set via `admin-session-lifetime` variable in our infrastructure repo's
terraform configuration file. For example:
`/systems/maven/mono/{region}/{environment}/main.tf`.
If it does not find one, it refers to the default set in
`AdminConfig.permanent_session_lifetime`.

## Contributing
See [CONTRIBUTING](CONTRIBUTING.md).
