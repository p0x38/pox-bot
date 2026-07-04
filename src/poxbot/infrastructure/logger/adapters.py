from __future__ import annotations

from logging import LoggerAdapter

from opentelemetry import trace

from .enrich import enrich_extra


class PrefixAdapter(LoggerAdapter):
    def process(self, msg, kwargs):
        span = trace.get_current_span()
        ctx = span.get_span_context()
        
        extra = dict(self.extra or {})

        if ctx.is_valid:
            extra["trace_id"] = format(ctx.trace_id, "032x")
        
        kwargs["extra"] = enrich_extra(kwargs.get("extra"))
        kwargs["extra"].update(extra)
        
        return msg, kwargs
