class SSHError(Exception):
    code = 502


class SSHConnectionError(SSHError):
    pass


class SSHAuthenticationError(SSHError):
    pass


class SSHTimeoutError(SSHError):
    code = 504


class SSHCommandError(SSHError):
    pass


def map_error(e: Exception) -> SSHError:
    import asyncssh
    msg = str(e)
    low = msg.lower()
    if isinstance(e, (SSHAuthenticationError,)):
        return e
    if isinstance(e, TimeoutError) or "timeout" in low or "timed out" in low:
        return SSHTimeoutError(f"Hết thời gian chờ SSH: {msg}")
    if "permission denied" in low or "authentication failed" in low or "no auth" in low:
        return SSHAuthenticationError(f"Xác thực SSH thất bại: {msg}")
    if isinstance(e, asyncssh.PermissionDenied):
        return SSHAuthenticationError(f"Xác thực SSH thất bại: {msg}")
    if "refused" in low or "unreachable" in low or "no route" in low or "name resolution" in low or "unknown host" in low:
        return SSHConnectionError(f"Kết nối SSH thất bại: {msg}")
    if isinstance(e, (OSError, asyncssh.Error)):
        return SSHConnectionError(f"Kết nối SSH thất bại: {msg}")
    return SSHCommandError(msg or "Lỗi SSH")
