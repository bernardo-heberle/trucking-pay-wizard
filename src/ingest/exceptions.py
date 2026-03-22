class IngestionError(Exception):
    """Raised when a document cannot be loaded or rendered."""


class UnsupportedFileTypeError(IngestionError):
    """Raised when the file extension is not in the supported set."""
