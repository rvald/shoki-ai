class OrchestratorError(Exception):
    pass

class RetryableError(OrchestratorError):
    """Temporary: network timeout, 429/5xx from upstream, transient GCS/IO errors."""
    pass

class PermanentError(OrchestratorError):
    """Won’t improve with retry: bad input, object not found, schema mismatch."""
    pass
