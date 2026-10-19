class IdempotencyConflict(ValueError):
    """An idempotency key was reused for a different operation."""


def resolve_receipt(receipt, run_id, command):
    """Return a stored response only when the receipt matches the exact operation.

    receipt is a (run_id, command, response) tuple fetched by globally unique key.
    Replaying a key across runs or across commands must never return another
    operation's success response.
    """
    if receipt is None:
        return None
    stored_run_id, stored_command, response = receipt
    if stored_run_id != run_id or stored_command != command:
        raise IdempotencyConflict(
            "idempotency key already used for a different run or command"
        )
    return response
