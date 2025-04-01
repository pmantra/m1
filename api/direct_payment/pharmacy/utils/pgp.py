import gnupg


class KeyImportError(Exception):
    pass


class DecryptionError(Exception):
    pass


def decrypt(
    encrypted_file_path: str,
    decrypted_file_path: str,
    passphrase: str,
    private_key: str,
    verbose: bool = False,
) -> bool:
    """Decrypts a file using a PGP private key and passphrase.

    Args:
        encrypted_file_path: The path to the file to encrypt.
        decrypted_file_path: The path to save the encrypted file to.
        passphrase: Passphrase used to generate private key
        private_key: Private key
        verbose: For debugging purpose
    Return:

    """
    gpg = gnupg.GPG(gnupghome="/tmp", verbose=verbose)
    imported_result = gpg.import_keys(private_key)
    if not imported_result.count:
        raise KeyImportError(f"Failed to import private key: {imported_result.stderr}")
    try:
        with open(encrypted_file_path, "rb") as fin:
            result = gpg.decrypt_file(
                fin,
                passphrase=passphrase,
                output=decrypted_file_path,
                always_trust=True,
                extra_args=["--ignore-mdc-error"],
            )
            if not result.ok:
                raise DecryptionError(f"Decryption failed: {result.stderr}")
            return result.ok
    except FileNotFoundError as e:
        raise e
