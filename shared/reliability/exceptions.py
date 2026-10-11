class PermanentMessageError(Exception):
    """
    Raised when a message is permanently invalid and must not be retried.

    Examples:
    - malformed event schema
    - missing mandatory fields
    - unsupported event contract
    - invalid event payload that cannot succeed on retry

    The caller should quarantine/DLQ the message and then ACK it.
    """