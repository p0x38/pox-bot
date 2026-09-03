from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio

from ...config.schema import TraceConfig


def setup_otel(config: TraceConfig, service_name: str):
    resource = Resource(
        {
            'service.name': service_name,
            'service.instance.id': 'p0x38-discord.py-bot',
        }
    )

    sampler = ParentBasedTraceIdRatio(config.sampling_ratio)
    tracer_provider = TracerProvider(resource=resource, sampler=sampler)

    trace_endpoint = config.otlp_traces_endpoint or config.opentelemetry_endpoint
    if trace_endpoint:
        if not trace_endpoint.startswith(('http://', 'https://')):
            trace_endpoint = f'http://{trace_endpoint}'

        tracer_provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=trace_endpoint, insecure=config.insecure),
                max_queue_size=config.max_batch_size * 4,
                max_export_batch_size=config.max_batch_size,
                schedule_delay_millis=config.export_interval_ms,
            ),
        )

    trace.set_tracer_provider(tracer_provider)

    readers = []

    metrics_endpoint = config.otlp_metrics_endpoint or config.opentelemetry_endpoint
    if metrics_endpoint:
        if not metrics_endpoint.startswith(('http://', 'https://')):
            metrics_endpoint = f'http://{metrics_endpoint}'

        readers.append(
            PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=metrics_endpoint, insecure=config.insecure),
                export_interval_millis=config.export_interval_ms,
            ),
        )

    readers.append(PrometheusMetricReader())

    meter_provider = MeterProvider(resource=resource, metric_readers=readers)
    metrics.set_meter_provider(meter_provider)

    return trace.get_tracer(f'{service_name}-tracer'), metrics.get_meter(
        f'{service_name}-metrics'
    )
