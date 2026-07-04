class SQLFileError(ValueError):
    """Raised when an SQL file cannot be loaded."""
    
    def __init__(self, path: str) -> None:
        super().__init__(f"Failed to load SQL file: {path}")
