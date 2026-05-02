from __future__ import annotations


class ExtractionError(Exception):
    """Raised when field extraction fails in an unrecoverable way.

    Non-retryable failures (bad API key, malformed request) raise this
    immediately.  Retryable failures (rate limits, network errors) raise this
    only after all retry attempts are exhausted.
    """


class MalformedToolResponse(Exception):
    """Raised when the model returns a tool response that violates the schema.

    For example: a field that should be ``{"value": "...", "confidence": ...}``
    is returned as a plain string.  The extractor treats this as a soft failure
    and retries.  If all retries are exhausted, the affected fields are
    reported as not found.
    """
