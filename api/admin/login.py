import flask_login as login
from otpauth import OtpAuth
from wtforms import fields, form, validators

from authn.domain.service import authn
from authn.models.user import User
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def init_login(application):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    login_manager = login.LoginManager()
    login_manager.init_app(application)

    # Create user loader function
    @login_manager.user_loader
    def load_user(user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return db.session.query(User).get(user_id)


class LoginForm(form.Form):
    email = fields.StringField(validators=[validators.DataRequired()])
    password = fields.PasswordField(validators=[validators.DataRequired()])
    totp = fields.StringField(validators=[validators.DataRequired()])

    def validate_totp(self, field):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self.get_user()

        if user is None:
            raise validators.ValidationError("Invalid user")

        if user.otp_secret is None:
            raise validators.ValidationError(
                "OTP is not set. Please, go through the otp set up."
            )

        auth = OtpAuth(user.otp_secret)
        if not auth.valid_totp(self.totp.data):
            raise validators.ValidationError("Invalid TOTP")

    def validate_email(self, field):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = self.get_user()

        if user is None:
            raise validators.ValidationError("Invalid user")
        if not authn.AuthenticationService().check_password(
            hashed_password=user.password,
            email=user.email,
            plaintext_password=self.password.data,
            user_id=user.id,
        ):
            raise validators.ValidationError("Invalid password")

    def get_user(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        user = db.session.query(User).filter_by(email=self.email.data).first()
        if user:
            return user
        elif user:
            log.debug(f"User {user} is not an admin!")
