import logging
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from source.config import config

logger = logging.getLogger('tracing')

def setup_tracing():
    """Initialize OpenTelemetry tracing"""
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

        # Create Jaeger exporter
        jaeger_exporter = JaegerExporter(
            collector_endpoint=config.tracing.jaeger_endpoint
        )

        # Add batch span processor
        span_processor = BatchSpanProcessor(jaeger_exporter)
        provider.add_span_processor(span_processor)

        logger.info(f"Tracing initialized for {config.tracing.service_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize tracing: {e}")
        return False