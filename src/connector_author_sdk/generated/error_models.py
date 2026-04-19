
# Generated from canonical contract schemas. Do not edit by hand.

from typing import Any, TypedDict


class ErrorPayload(TypedDict):
    code: str
    message: str
    retryable: bool
    request_id: str
    details: dict[str, Any]


class ErrorEnvelope(TypedDict):
    error: ErrorPayload


ERROR_REQUIRED_FIELDS = ['code', 'message', 'retryable', 'request_id', 'details']
