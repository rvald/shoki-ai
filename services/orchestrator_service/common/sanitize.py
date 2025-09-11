# common/sanitize.py
import hashlib
from typing import Any

SAFE_KEYS = {
    "bucket", "name", "generation", "user_id", "session_id",
    "model_name", "app_name", "url", "method",
}
SENSITIVE_KEYS = {
    "authorization", "api_key", "token", "password", "headers",
    "transcript", "text", "body", "new_message", "prompt",
}

def hash_preview(s: str, n: int = 12) -> str:
    if not isinstance(s, str):
        s = str(s)
    return f"sha256={hashlib.sha256(s.encode('utf-8')).hexdigest()[:n]},len={len(s)}"

def sanitize_value(key: str, value: Any) -> Any:
    k = (key or "").lower()
    if k in SAFE_KEYS:
        return value
    if k in SENSITIVE_KEYS:
        # Never log raw; return only hash/length
        return hash_preview(str(value))
    # Heuristic: large strings/bytes → show hash/len; small scalars/loggable dicts/lists → keep
    if isinstance(value, (bytes, bytearray)):
        return f"bytes:{len(value)}"
    if isinstance(value, str):
        return value if len(value) <= 120 else hash_preview(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    # For dict/list, shallow-sanitize children
    if isinstance(value, dict):
        return {k: sanitize_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_value("", v) for v in value]
    return str(value)