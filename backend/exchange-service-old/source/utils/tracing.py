# source/utils/tracing.py
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from source.config import config

logger = logging.getLogger('tracing')

def setup_tracing():
    """Initialize OpenTelemetry tracing with OTLP exporter"""
    if not config.tracing.enabled:
        logger.info("Tracing is disabled")
        return False

    try:
        # Create resource with service name
        resource = Resource(attributes={
            SERVICE_NAME: config.tracing.service_name
        })

        # Set up trace provider
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)

        # Create OTLP exporter (replaces Jaeger exporter)
        otlp_exporter = OTLPSpanExporter(
            endpoint="http://jaeger-collector:4317",  # gRPC endpoint
            insecure=True  # For development environments
        )

        # Add batch span processor
        span_processor = BatchSpanProcessor(otlp_exporter)
        provider.add_span_processor(span_processor)

        logger.info(f"OTLP tracing initialized for {config.tracing.service_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize tracing: {e}")
        return False