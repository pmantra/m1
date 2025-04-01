import base64
import hashlib
import hmac
import json
import secrets

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

from Crypto.Cipher import AES

kek_metadata_key_name = "key"
dek_metadata_key_name = "dek"
nonce_metadata_key_name = "nonce"
hash_metadata_key_name = "hash"
sig_metadata_key_name = "sig"
sig_key_metadata_key_name = "sigKey"

metadata_required_keys = frozenset(
    [
        kek_metadata_key_name,
        dek_metadata_key_name,
        nonce_metadata_key_name,
        hash_metadata_key_name,
        sig_metadata_key_name,
        sig_key_metadata_key_name,
    ]
)
metadata_signature_keys = frozenset(
    [
        kek_metadata_key_name,
        dek_metadata_key_name,
        nonce_metadata_key_name,
        hash_metadata_key_name,
        sig_key_metadata_key_name,
    ]
)

dek_byte_length = 32
auth_tag_byte_length = 16  # This is for compatibility with Go's `crypto.cipher.AEAD`
nonce_byte_length = 12  # This is for compatibility with Go's `crypto.cipher.AEAD`


def _fingerprint_metadata(metadata):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    sanitized = {}
    for key in metadata_signature_keys:
        sanitized[key] = metadata[key]

    encoded = json.dumps(
        sanitized, indent=None, separators=(",", ":"), sort_keys=True
    )  # N.B. - This is for compatibility with `json.Marshal` in Go which sorts keys and uses no whitespace.

    return hashlib.sha256(encoded.encode("UTF-8")).digest()


def _sign_metadata(client, key_name, metadata):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    fingerprint = _fingerprint_metadata(metadata)

    request = {"name": key_name, "digest": {"sha256": fingerprint}}
    response = client.asymmetric_sign(request=request)

    return response.signature


def _encrypt(client, kek_name, cleartext):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    nonce = secrets.token_bytes(nonce_byte_length)
    dek = secrets.token_bytes(dek_byte_length)

    cipher = AES.new(dek, AES.MODE_GCM, nonce=nonce, mac_len=auth_tag_byte_length)
    ciphertext, tag = cipher.encrypt_and_digest(cleartext)

    ciphertext += tag  # N.B. - This is for compatibility with AES-GCM in Go which automatically appends the MAC tag to the end of the ciphertext.

    response = client.encrypt(request={"name": kek_name, "plaintext": dek})
    encrypted_dek = response.ciphertext

    return (ciphertext, encrypted_dek, nonce)


def put_encrypted_object(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    gcs_client,
    kms_client,
    bucket_name,
    object_name,
    kek_name,
    signing_key_name,
    cleartext,
):
    """Encrypts the given cleartext with envelope encryption using the given KEK
    before uploading the encrypted data to the given object name in the given
    bucket name.

    :param  gcs_client: An initialized GCS client instance.
    :type gcs_client: google.cloud.storage.Client
    :param  kms_client: An initialized KMS client instance.
    :type kms_client: google.cloud.kms.KeyManagementServiceClient
    :param bucket_name: The name of the GCS bucket holding the encrypted object.
    :type bucket_name: str
    :param object_name: THe name of the object to write.
    :type bucket_name: str
    :param kek_name: The fully qualified name of the KMS key to use as the KEK.
    :type bucket_name: str
    :param signing_key_name: The fully qualified name of the KMS key to use for metadata signing.
    :type bucket_name: str
    :param cleartext: The unencrypted data to upload to the bucket.
    :type bucket_name: str
    :return: the hex-encoded SHA-256 hashcode of the unencrypted contents.
    :rtype: str
    """
    try:
        encoded_cleartext = cleartext.encode("UTF-8")
    except AttributeError:
        encoded_cleartext = cleartext

    ciphertext, encrypted_dek, nonce = _encrypt(kms_client, kek_name, encoded_cleartext)

    unpadded_dek = (
        base64.b64encode(encrypted_dek).rstrip(b"=").decode()
    )  # N.B. - This rstrip for compatibility with `base64.RawStdEncoding` in Go which uses no pad.
    unpadded_nonce = (
        base64.b64encode(nonce).rstrip(b"=").decode()
    )  # N.B. - This rstrip for compatibility with `base64.RawStdEncoding` in Go which uses no pad.
    hashcode = hashlib.sha256(encoded_cleartext).hexdigest()

    metadata = {
        kek_metadata_key_name: kek_name,
        dek_metadata_key_name: unpadded_dek,
        nonce_metadata_key_name: unpadded_nonce,
        hash_metadata_key_name: hashcode,
        sig_key_metadata_key_name: signing_key_name,
    }

    signature = _sign_metadata(kms_client, signing_key_name, metadata)
    unpadded_signature = (
        base64.b64encode(signature).rstrip(b"=").decode()
    )  # N.B. - This rstrip for compatibility with `base64.RawStdEncoding` in Go which uses no pad.
    metadata[sig_metadata_key_name] = unpadded_signature

    bucket = gcs_client.bucket(bucket_name)
    obj = bucket.blob(object_name)

    obj.metadata = metadata
    obj.upload_from_string(ciphertext, content_type="application/octet-stream")

    return hashcode


def _pad_encoded_value(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if len(value) % 4:
        value += "=" * (4 - (len(value) % 4))

    return value


def _validate_metadata(client, metadata):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for key in metadata_required_keys:
        if key not in metadata:
            raise ValueError(f"Missing metadata key: {key}")

    sig_key_name = metadata[sig_key_metadata_key_name]
    encoded_signature = _pad_encoded_value(metadata[sig_metadata_key_name])
    signature = base64.b64decode(encoded_signature)

    public_key = client.get_public_key(request={"name": sig_key_name})
    pem = public_key.pem.encode("utf-8")
    ec_key = serialization.load_pem_public_key(pem, default_backend())

    fingerprint = _fingerprint_metadata(metadata)

    sha256 = hashes.SHA256()
    ec_key.verify(signature, fingerprint, ec.ECDSA(utils.Prehashed(sha256)))  # type: ignore[union-attr,call-arg,arg-type] # Item "DHPublicKey" of "Union[DHPublicKey, DSAPublicKey, RSAPublicKey, EllipticCurvePublicKey, Ed25519PublicKey, Ed448PublicKey, X25519PublicKey, X448PublicKey]" has no attribute "verify" #type: ignore[union-attr] # Item "X25519PublicKey" of "Union[DHPublicKey, DSAPublicKey, RSAPublicKey, EllipticCurvePublicKey, Ed25519PublicKey, Ed448PublicKey, X25519PublicKey, X448PublicKey]" has no attribute "verify" #type: ignore[union-attr] # Item "X448PublicKey" of "Union[DHPublicKey, DSAPublicKey, RSAPublicKey, EllipticCurvePublicKey, Ed25519PublicKey, Ed448PublicKey, X25519PublicKey, X448PublicKey]" has no attribute "verify" #type: ignore[call-arg] # Missing positional argument "algorithm" in call to "verify" of "RSAPublicKey" #type: ignore[call-arg] # Too many arguments for "verify" of "Ed25519PublicKey" #type: ignore[call-arg] # Too many arguments for "verify" of "Ed448PublicKey" #type: ignore[arg-type] # Argument 3 to "verify" of "DSAPublicKey" has incompatible type "ECDSA"; expected "Union[Prehashed, HashAlgorithm]" #type: ignore[arg-type] # Argument 3 to "verify" of "RSAPublicKey" has incompatible type "ECDSA"; expected "AsymmetricPadding" #type: ignore[call-arg] # Missing positional argument "algorithm" in call to "verify" of "RSAPublicKey" #type: ignore[call-arg] # Too many arguments for "verify" of "Ed25519PublicKey" #type: ignore[call-arg] # Too many arguments for "verify" of "Ed448PublicKey" #type: ignore[arg-type] # Argument 3 to "verify" of "DSAPublicKey" has incompatible type "ECDSA"; expected "Union[Prehashed, HashAlgorithm]" #type: ignore[arg-type] # Argument 3 to "verify" of "RSAPublicKey" has incompatible type "ECDSA"; expected "AsymmetricPadding"

    encoded_nonce = _pad_encoded_value(metadata[nonce_metadata_key_name])
    nonce = base64.b64decode(encoded_nonce)

    encoded_dek = _pad_encoded_value(metadata[dek_metadata_key_name])
    encrypted_dek = base64.b64decode(encoded_dek)

    hashcode = bytes.fromhex(metadata[hash_metadata_key_name])

    return (metadata[kek_metadata_key_name], encrypted_dek, nonce, hashcode)


def _decrypt(client, key_name, encrypted_dek, nonce, ciphertext_and_tag):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    response = client.decrypt(request={"name": key_name, "ciphertext": encrypted_dek})

    auth_tag = ciphertext_and_tag[len(ciphertext_and_tag) - auth_tag_byte_length :]
    ciphertext = ciphertext_and_tag[: len(ciphertext_and_tag) - auth_tag_byte_length]
    dek = response.plaintext

    cipher = AES.new(dek, AES.MODE_GCM, nonce=nonce, mac_len=auth_tag_byte_length)
    return cipher.decrypt_and_verify(ciphertext, auth_tag)


def get_encrypted_object(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    gcs_client, kms_client, bucket_name, object_name, compatibility=True
):
    """Downloads the given object from the given bucket and decrypts
    it using envelope encryption details stored in the object metadata.

    :param  gcs_client: An initialized GCS client instance.
    :type gcs_client: google.cloud.storage.Client
    :param  kms_client: An initialized KMS client instance.
    :type kms_client: google.cloud.kms.KeyManagementServiceClient
    :param bucket_name: The name of the GCS bucket holding the encrypted object.
    :type bucket_name: str
    :param object_name: THe name of the object to write.
    :type bucket_name: str
    :param compatibility: Support legacy unencrypted objects.
    :type compatibility: bool
    :return: A tuple of the unencrypted data from the object and its metadata.
    :rtype: tuple(str, dict)
    """
    bucket = gcs_client.bucket(bucket_name)
    blob = bucket.get_blob(object_name)

    if blob is None:
        raise ValueError(f"object does not exist: gs://{bucket_name}/{object_name}")

    metadata = blob.metadata

    if compatibility and (metadata is None or dek_metadata_key_name not in metadata):
        return (blob.download_as_string(), metadata)

    (kek_name, encrypted_dek, nonce, hashcode) = _validate_metadata(
        kms_client, metadata
    )

    ciphertext = blob.download_as_string()
    cleartext = _decrypt(kms_client, kek_name, encrypted_dek, nonce, ciphertext)

    computed_hashcode = hashlib.sha256(cleartext).digest()
    if not hmac.compare_digest(hashcode, computed_hashcode):
        raise ValueError(
            f"data hashcode comparison failed: expected {hashcode} but found {computed_hashcode}"  # type: ignore[str-bytes-safe] # If x = b`abc` then f"{x}" or "{}".format(x) produces "b`abc`", not "abc". If this is desired behavior, use f"{x!r}" or "{!r}".format(x). Otherwise, decode the bytes
        )

    return (cleartext, metadata)
