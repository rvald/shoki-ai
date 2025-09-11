import contextvars
from typing import Optional, Tuple

_correlation_id = contextvars.ContextVar("correlation_id", default=None)
_idempotency_key = contextvars.ContextVar("idempotency_key", default=None)

def set_context(correlation_id: Optional[str], idempotency_key: Optional[str]) -> None:
    _correlation_id.set(correlation_id) # type: ignore
    _idempotency_key.set(idempotency_key) # type: ignore

def get_context() -> Tuple[Optional[str], Optional[str]]:
    return _correlation_id.get(), _idempotency_key.get()