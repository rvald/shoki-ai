from opentelemetry import trace
import os, logging, time, json

SERVICE_NAME = os.getenv("SERVICE_NAME", "unknown-service")
ENV = os.getenv("ENVIRONMENT", "local")

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
_logger = logging.getLogger(SERVICE_NAME)

def jlog(event: str = "", severity: str = "INFO", **fields):
    span = trace.get_current_span()
    ctx = span.get_span_context() if span else None
    trace_id = f"{ctx.trace_id:032x}" if ctx and ctx.trace_id else None
    span_id = f"{ctx.span_id:016x}" if ctx and ctx.span_id else None

    record = {
        "event": event,
        "severity": severity,
        "service": SERVICE_NAME,
        "env": ENV,
        "ts": time.time(),
        "trace_id": trace_id,
        "span_id": span_id,
    }
    record.update(fields)
    _logger.log(getattr(logging, severity, logging.INFO), json.dumps(record, ensure_ascii=False))