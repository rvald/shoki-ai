# common/otel.py
import os
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

USE_CLOUD_TRACE = os.getenv("USE_CLOUD_TRACE", "true").lower() == "true"

def init_tracing(app, service_name: str, service_version: str = "v1"):
    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
        "deployment.environment": os.getenv("ENVIRONMENT", "dev"),
    })
    provider = TracerProvider(resource=resource)
    if USE_CLOUD_TRACE:
        # pip: opentelemetry-exporter-gcp-trace
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
        exporter = CloudTraceSpanExporter()
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Auto-instrument frameworks/clients
    FastAPIInstrumentor().instrument_app(app)

    return trace.get_tracer(service_name)