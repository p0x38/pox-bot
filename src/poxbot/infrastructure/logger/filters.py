from logging import Filter, LogRecord


class ExcludeConsoleFilter(Filter):
    def filter(self, record: LogRecord):
        return not getattr(record, "no_console", False)


class SkipEmptyMessageFilter(Filter):
    def filter(self, record: LogRecord):
        return not (not record.msg or not str(record.msg).strip())
