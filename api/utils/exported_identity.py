import base64
import binascii
import os

from sqlalchemy.inspection import inspect

from Crypto.Cipher import AES

_ENV = "EXPORTED_IDENTITY_SECRET_KEY"
_EXPORTED_IDENTITY_SECRET_KEY_B64 = os.getenv(_ENV)
_ERR = (
    f'Please define environment variable "{_ENV}" to enable identity exporting. '
    f"This value will function as the 32 byte aes-siv secret key for encrypting "
    f"identities exported outside of the backend data system. Generate with: "
    f"base64 <(cat /dev/urandom | head -c 32);"
)
_KEY = None


def _assert_active_key():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    global _KEY
    if _KEY is not None:
        return _KEY
    if _EXPORTED_IDENTITY_SECRET_KEY_B64 is None:
        raise RuntimeError(_ERR)
    try:
        key = base64.b64decode(_EXPORTED_IDENTITY_SECRET_KEY_B64, validate=True)
    except binascii.Error:
        raise RuntimeError(_ERR)
    if len(key) != 32:
        raise RuntimeError(_ERR)
    _KEY = key


def obfuscate(model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """obfuscate creates a token representing the identity of a given model instance.

    The token is created by joining the model class name and all of its primary keys with ':'. For example, the user
    with an id of 1 will have the identity token 'User:1'. That token is then deterministically encrypted using AES in
    Synthetic Initialization Vector (SIV) mode so that equal encrypted tokens represent the same database record. The
    ciphertext's length will be a multiple of 16 bytes, proportional to the plaintext's length. In cases where primary
    keys can have variable length this may reveal information about the underlying identities.

    To recover an encrypted identity, pass the encrypted token to the decrypt_identity function in the dev shell.
    """
    model_name = type(model).__name__
    primary_keys = (str(k) for k in inspect(model).identity)
    identity_token = f'{model_name}:{":".join(primary_keys)}'
    return encrypt_identity(identity_token)


def encrypt_identity(token):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Parse the secret key from the environment
    _assert_active_key()

    # Encode the token as ascii bytes
    token = token.encode("ascii")

    # AES-SIV encrypt the token bytes, producing a ciphertext and a MAC
    cipher = AES.new(_KEY, AES.MODE_SIV)
    ciphertext, mac = cipher.encrypt_and_digest(token)
    assert len(mac) == 16

    # Base64 encode the concatenated components with a URL safe character set
    token = base64.urlsafe_b64encode(ciphertext + mac).decode("ascii")

    return token


def decrypt_identity(token):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Parse the secret key from the environment
    _assert_active_key()

    # Decode the token back into the concatenated ciphertext and MAC
    token = base64.urlsafe_b64decode(token)

    # Split the components assuming the MAC has a fixed length of 16 bytes
    ciphertext = token[:-16]
    mac = token[-16:]

    # AES-SIV decrypt and verify the ciphertext and mac into the plaintext token bytes
    cipher = AES.new(_KEY, AES.MODE_SIV)
    token = cipher.decrypt_and_verify(ciphertext, mac)

    # Decode the token bytes back into an ascii string
    token = token.decode("ascii")

    return token  # model_name:pk1:pk2:...:pkn
