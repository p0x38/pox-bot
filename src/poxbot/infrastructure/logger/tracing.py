from contextlib import contextmanager

from opentelemetry import trace

from .context import get_request_id

tracer = trace.get_tracer('pox-discord-bot-tracer')


@contextmanager
def start_span(name: str):
    with tracer.start_as_current_span(name) as span:
        try:
            rid = get_request_id()
            if rid:
                span.set_attribute('request_id', rid)

            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR))


def traced(name: str):
    def decorator(fn):
        async def wrapper(*args, **kwargs):
            with start_span(name):
                return await fn(*args, **kwargs)

        return wrapper

    return decorator
