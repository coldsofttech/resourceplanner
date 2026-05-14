import base64
import hashlib
import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

_ENC_PREFIX = 'enc:'
_AWSSM_PREFIX = 'awssm:'
_AWSSM_NAME_PREFIX = 'resourceplanner/configurations/'


def get_secrets_source() -> str:
    """Return 'aws' or 'local' based on SECRETS_SOURCE environment variable."""
    source = os.environ.get('SECRETS_SOURCE', 'local').strip().lower()
    return 'aws' if source == 'aws' else 'local'


@lru_cache(maxsize=1)
def _get_fernet():
    from cryptography.fernet import Fernet
    from django.conf import settings
    raw = settings.SECRET_KEY.encode('utf-8')
    derived = hashlib.sha256(raw).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_value(plaintext: str, code: str) -> str:
    """
    Encrypt plaintext for secure DB storage.
    Routes to Fernet (local) or AWS Secrets Manager (aws) based on SECRETS_SOURCE.
    Empty strings are returned unchanged.
    """
    if not plaintext:
        return plaintext
    if get_secrets_source() == 'aws':
        return _aws_put(code, plaintext)
    return _fernet_encrypt(plaintext)


def decrypt_value(stored: str, code: str) -> str:
    """
    Decrypt a value previously produced by encrypt_value.
    Handles enc: (local Fernet), awssm: (AWS SM), and legacy plain-text values.
    """
    if not stored:
        return stored
    if stored.startswith(_ENC_PREFIX):
        return _fernet_decrypt(stored[len(_ENC_PREFIX):])
    if stored.startswith(_AWSSM_PREFIX):
        return _aws_get(stored[len(_AWSSM_PREFIX):])
    return stored  # legacy plain text — pass through


def is_encrypted(stored: str) -> bool:
    return bool(stored) and (
        stored.startswith(_ENC_PREFIX) or stored.startswith(_AWSSM_PREFIX)
    )


def delete_secret(code: str, stored: str) -> None:
    """Remove the backing secret store entry if one exists (used on reset to default)."""
    if stored and stored.startswith(_AWSSM_PREFIX):
        _aws_delete(stored[len(_AWSSM_PREFIX):])


# --- Local Fernet helpers ---

def _fernet_encrypt(plaintext: str) -> str:
    token = _get_fernet().encrypt(plaintext.encode('utf-8')).decode('utf-8')
    return f'{_ENC_PREFIX}{token}'


def _fernet_decrypt(token: str) -> str:
    try:
        return _get_fernet().decrypt(token.encode('utf-8')).decode('utf-8')
    except Exception:
        logger.error('Local Fernet decryption failed — returning empty string.')
        return ''


# --- AWS Secrets Manager helpers ---

def _aws_secret_name(code: str) -> str:
    return f'{_AWSSM_NAME_PREFIX}{code}'


def _aws_put(code: str, plaintext: str) -> str:
    import boto3
    from botocore.exceptions import ClientError

    name = _aws_secret_name(code)
    client = boto3.client('secretsmanager')
    try:
        client.put_secret_value(SecretId=name, SecretString=plaintext)
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            client.create_secret(Name=name, SecretString=plaintext)
        else:
            raise
    return f'{_AWSSM_PREFIX}{name}'


def _aws_get(secret_name: str) -> str:
    import boto3
    from botocore.exceptions import ClientError

    client = boto3.client('secretsmanager')
    try:
        resp = client.get_secret_value(SecretId=secret_name)
        return resp.get('SecretString', '')
    except ClientError:
        logger.exception("Failed to retrieve secret '%s' from AWS Secrets Manager.", secret_name)
        return ''


def _aws_delete(secret_name: str) -> None:
    import boto3
    from botocore.exceptions import ClientError

    client = boto3.client('secretsmanager')
    try:
        client.delete_secret(SecretId=secret_name, ForceDeleteWithoutRecovery=True)
    except ClientError as e:
        code = e.response['Error']['Code']
        if code not in ('ResourceNotFoundException', 'InvalidRequestException'):
            logger.warning("Could not delete AWS secret '%s': %s", secret_name, e)
