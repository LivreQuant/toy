# source/utils/tracing.py
import logging
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

from source.config import config

logger = logging.getLogger('tracing')


def setup_tracing():
    """Initialize OpenTelemetry tracing with OTLP exporter"""
    # Check if tracing is enabled
    if not config.tracing.enabled:
        logger.info("Tracing is disabled, using no-op tracer")
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        return True

    service_name = config.tracing.service_name
    otlp_endpoint = config.tracing.exporter_endpoint

    try:
        # Set up tracer provider with service name resource
        resource = Resource(attributes={
            SERVICE_NAME: service_name
        })

        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)

        try:
            # Create OTLP exporter and add it to the tracer provider
            otlp_exporter = OTLPSpanExporter(
                endpoint=otlp_endpoint,
                insecure=True  # Use insecure for local development
            )

            # Process spans in batches for better performance
            span_processor = BatchSpanProcessor(otlp_exporter)
            provider.add_span_processor(span_processor)
            
            logger.info(f"OTLP exporter configured for endpoint: {otlp_endpoint}")
        except Exception as export_error:
            logger.warning(f"Failed to set up OTLP exporter: {export_error}")
            # Continue with no-op tracing
            return True

        # Instrument HTTP client and database
        try:
            AioHttpClientInstrumentor().instrument()
            AsyncPGInstrumentor().instrument()
            logger.info("Auto-instrumentation enabled for aiohttp and asyncpg")
        except Exception as inst_error:
            logger.warning(f"Failed to set up auto-instrumentation: {inst_error}")

        logger.info(f"Tracing initialized for service {service_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize tracing: {e}")
        # Ensure we have a valid no-op tracer if initialization fails
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        return False


@contextmanager
def optional_trace_span(tracer, name, attributes=None):
    """
    Context manager for optional tracing that works whether tracing is enabled or not.

    Args:
        tracer: The tracer object
        name: Name of the span
        attributes: Optional dictionary of initial attributes to set

    Example:
        with optional_trace_span(self.tracer, "operation_name") as span:
            # Do work
            span.set_attribute("key", "value")  # No-op if tracing disabled
    """
    class DummySpan:
        def set_attribute(self, key, value): pass
        def record_exception(self, exception): pass
        def add_event(self, name, attributes=None): pass
        def set_status(self, status): pass

    try:
        with tracer.start_as_current_span(name) as span:
            # Set initial attributes if provided
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            yield span
    except Exception as e:
        # Log only if it's an unexpected error
        if str(e) != "No TracerProvider configured":
            logger.debug(f"Tracing disabled or failed: {e}")
        
        # Return dummy span
        dummy = DummySpan()
        yield dummy