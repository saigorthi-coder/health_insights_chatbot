"""Utils for redirecting OpenAI Agent SDK traces to LangFuse via OpenTelemetry.

Full documentation:
langfuse.com/docs/integrations/openaiagentssdk/openai-agents
"""

import nest_asyncio
from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from .otlp_env_setup import set_up_langfuse_otlp_env_vars


def configure_oai_agents_sdk(service_name: str) -> None:
    """Initialize OpenAI Agents tracing instrumentation."""
    nest_asyncio.apply()
    _ = service_name
    OpenAIAgentsInstrumentor().instrument()


def setup_langfuse_tracer(service_name: str = "agents_sdk") -> "trace.Tracer":
    """Register Langfuse as the default tracing provider and return tracer.

    Returns
    -------
    tracer: OpenTelemetry Tracer
    """
    set_up_langfuse_otlp_env_vars()
    configure_oai_agents_sdk(service_name)

    # Create a TracerProvider for OpenTelemetry
    trace_provider = TracerProvider()

    # Add a SimpleSpanProcessor with the OTLPSpanExporter to send traces
    trace_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))

    # Set the global default tracer provider
    trace.set_tracer_provider(trace_provider)
    return trace.get_tracer(__name__)
