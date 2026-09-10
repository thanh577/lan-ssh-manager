"""Build asyncssh connect kwargs from a Machine row. API never touches asyncssh directly."""
import asyncssh
from ...core.security import decrypt_secret
from ...core.config import get_settings


def build_connect_kwargs(machine) -> dict:
    s = get_settings()
    kw: dict = {
        "host": machine.hostname,
        "port": machine.port or 22,
        "username": machine.username,
        "known_hosts": None,  # LAN MVP: auto-accept host keys (documented). Harden later with known_hosts file.
        "connect_timeout": s.SSH_TIMEOUT,
    }
    secret = ""
    if machine.credential_encrypted:
        try:
            secret = decrypt_secret(machine.credential_encrypted)
        except Exception as e:
            raise ValueError("Không giải mã được thông tin đăng nhập SSH")
    if machine.auth_type == "key":
        kw["client_keys"] = None
        if secret:
            # asyncssh accepts key data via private key string list
            import io
            try:
                kw["client_keys"] = [asyncssh.import_private_key(secret)]
            except Exception:
                # fallback: treat as key file content handled by agent? raise clear error
                raise ValueError("Private key không đúng định dạng")
        # allow ssh-agent fallback when no key stored? keep simple: no password
    else:
        kw["password"] = secret or None
    return kw
