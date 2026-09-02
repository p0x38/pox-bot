class AIError(Exception):
    pass


class EmptyInput(AIError):  # ruff: ignore[error-suffix-on-exception-name]
    def __init__(self, *args):
        super().__init__("Input data must not be empty", *args)


class MissingInput(AIError):  # ruff: ignore[error-suffix-on-exception-name]
    def __init__(self, *args):
        super().__init__("Some of data are missing", *args)


class InvalidData(AIError):  # ruff: ignore[error-suffix-on-exception-name]
    def __init__(self, *args):
        super().__init__("Some of data type is not correctly typed", *args)


class InvalidQueryData(AIError):  # ruff: ignore[error-suffix-on-exception-name]
    def __init__(self, *args):
        super().__init__("Query data is not valid", *args)


class UnknownProvider(AIError):  # ruff: ignore[error-suffix-on-exception-name]
    def __init__(self, *args):
        super().__init__("Provider is not known", *args)


class NotImplementedProvider(AIError):  # ruff: ignore[error-suffix-on-exception-name]
    def __init__(self, *args):
        super().__init__("This provider is not available yet", *args)
