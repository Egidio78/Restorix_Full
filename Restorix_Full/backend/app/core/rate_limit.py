"""Rate limit configuration using slowapi."""
from slowapi import Limiter
from slowapi.util import get_remote_address


def user_key(request) -> str:
    """Rate limit key: per-user when authenticated, else per-IP."""
    user = getattr(request.state, 'user', None)
    if user is not None:
        uid = getattr(user, 'id', None)
        if uid is not None:
            return f'user:{uid}'
    return get_remote_address(request)


limiter = Limiter(key_func=user_key)
