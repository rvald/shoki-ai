# common/log_calls.py
import asyncio
import inspect
import time
from functools import wraps
from typing import Any, Callable, Dict

from ..src.logging import jlog  # your JSON logger
from .context import get_context
from .sanitize import sanitize_value

CALL_LOGGER_ENABLED = True  # or read from env if you prefer

def _bind_args(func: Callable, *args, **kwargs) -> Dict[str, Any]:
    sig = inspect.signature(func)
    bound = sig.bind_partial(*args, **kwargs)
    bound.apply_defaults()
    return dict(bound.arguments)

def log_calls(name: str | None = None):
    """
    Structured call logger for sync/async functions.
    - Logs start/end/error with sanitized args and duration_ms.
    - Injects correlation_id/idempotency_key from contextvars.
    """
    def decorator(func: Callable):
        func_name = name or func.__name__
        is_coro = asyncio.iscoroutinefunction(func)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not CALL_LOGGER_ENABLED:
                return await func(*args, **kwargs)

            start = time.time()
            argmap = _bind_args(func, *args, **kwargs)
            san_args = {k: sanitize_value(k, v) for k, v in argmap.items()}
            cid, idem = get_context()
            jlog(event="call_start", fn=func_name, args=san_args,
                 correlation_id=cid, idempotency_key=idem)

            try:
                result = await func(*args, **kwargs)
                dur = int((time.time() - start) * 1000)
                # Preview return value safely
                san_ret = sanitize_value("return", result)
                jlog(event="call_end", fn=func_name, duration_ms=dur, ret=san_ret,
                     correlation_id=cid, idempotency_key=idem)
                return result
            except Exception as e:
                dur = int((time.time() - start) * 1000)
                jlog(event="call_error", fn=func_name, duration_ms=dur, error=str(e),
                     correlation_id=cid, idempotency_key=idem, severity="ERROR")
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not CALL_LOGGER_ENABLED:
                return func(*args, **kwargs)

            start = time.time()
            argmap = _bind_args(func, *args, **kwargs)
            san_args = {k: sanitize_value(k, v) for k, v in argmap.items()}
            cid, idem = get_context()
            jlog(event="call_start", fn=func_name, args=san_args,
                 correlation_id=cid, idempotency_key=idem)

            try:
                result = func(*args, **kwargs)
                dur = int((time.time() - start) * 1000)
                san_ret = sanitize_value("return", result)
                jlog(event="call_end", fn=func_name, duration_ms=dur, ret=san_ret,
                     correlation_id=cid, idempotency_key=idem)
                return result
            except Exception as e:
                dur = int((time.time() - start) * 1000)
                jlog(event="call_error", fn=func_name, duration_ms=dur, error=str(e),
                     correlation_id=cid, idempotency_key=idem, severity="ERROR")
                raise

        return async_wrapper if is_coro else sync_wrapper
    return decorator