# source/utils/tracing.py
import logging
import os
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

logger = logging.getLogger('tracing')


def setup_tracing():
    """Initialize OpenTelemetry tracing with Jaeger exporter"""
    # Check if tracing is enabled (default to true)
    if os.getenv('ENABLE_TRACING', 'true').lower() != 'true':
        logger.info("Tracing is disabled, using no-op tracer")
        # Set up a no-op tracer provider
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        return True

    service_name = os.getenv('OTEL_SERVICE_NAME', 'fund-service')
    jaeger_endpoint = os.getenv('OTEL_EXPORTER_JAEGER_ENDPOINT', 'http://jaeger-collector:14268/api/traces')

    try:
        # Set up tracer provider with service name resource
        resource = Resource(attributes={
            SERVICE_NAME: service_name
        })

        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)

        # Create Jaeger exporter and add it to the tracer provider
        jaeger_exporter = JaegerExporter(
            collector_endpoint=jaeger_endpoint,
        )

        # Process spans in batches for better performance
        span_processor = BatchSpanProcessor(jaeger_exporter)
        provider.add_span_processor(span_processor)

        # Instrument HTTP client and database
        AioHttpClientInstrumentor().instrument()
        AsyncPGInstrumentor().instrument()

        logger.info(f"Tracing initialized for service {service_name}, exporting to {jaeger_endpoint}")
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
    try:
        with tracer.start_as_current_span(name) as span:
            # Set initial attributes if provided
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            yield span
    except Exception as e:
        # If tracing fails or is disabled, return a dummy span object
        class DummySpan:
            def set_attribute(self, key, value):
                pass

            def record_exception(self, exception):
                pass

            def add_event(self, name, attributes=None):
                pass

            def set_status(self, status):
                pass

        # Log only if it's an unexpected error, not if tracing is just disabled
        if str(e) != "No TracerProvider configured":
            logger.debug(f"Tracing disabled or failed: {e}")

        dummy = DummySpan()
        yield dummy
