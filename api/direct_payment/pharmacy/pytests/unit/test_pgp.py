import tempfile

import gnupg
import pytest

from direct_payment.pharmacy.utils.pgp import DecryptionError, KeyImportError, decrypt


@pytest.fixture
def gpg():
    return gnupg.GPG(gnupghome="/tmp")


def setup_gpg_key(gpg):
    input = gpg.gen_key_input(name_email="foo@bar.com", passphrase="foobar")
    key = gpg.gen_key(input)
    return key


@pytest.fixture
def encrypted(gpg):
    key = setup_gpg_key(gpg)
    original_data = b"Hello"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".gpg") as temp_file:
        gpg.encrypt(original_data, key.fingerprint, output=temp_file.name)
        yield temp_file.name


@pytest.fixture
def private_key(gpg):
    key = setup_gpg_key(gpg)
    return gpg.export_keys(key.fingerprint)


def test_decrypt(gpg, encrypted, private_key):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_decrypted:
        result = decrypt(encrypted, temp_decrypted.name, "foobar", private_key)
        assert result

        with open(temp_decrypted.name, "rb") as f:
            decrypted_data = f.read()
        assert decrypted_data == b"Hello"


def test_non_existent_file(gpg, private_key):
    with tempfile.NamedTemporaryFile(delete=True) as temp:
        with pytest.raises(FileNotFoundError):
            decrypt("non_exist_file.gpg", temp.name, "foo", private_key)


def test_incorrect_passphrase(gpg, encrypted, private_key):
    with tempfile.NamedTemporaryFile(delete=True) as temp:
        with pytest.raises(DecryptionError):
            decrypt(encrypted, temp.name, "", private_key)


def test_invalid_private_key(gpg, encrypted):
    invalid_key = "invalid private key"
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        with pytest.raises(KeyImportError):
            decrypt(encrypted, temp.name, "foobar", invalid_key)
