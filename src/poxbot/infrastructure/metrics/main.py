from .metrics import Metrics

from .provider import setup_otel

from ...config.schema import TraceConfig

metrics: Metrics | None = None

def create_metrics(config: TraceConfig, service_name: str = "pox-discord-bot") -> Metrics:
    global metrics  # noqa: PLW0602
    if metrics is not None:
        return metrics
    
    tracer, meter = setup_otel(config, service_name)
    return Metrics(config=config, tracer=tracer, meter=meter)
