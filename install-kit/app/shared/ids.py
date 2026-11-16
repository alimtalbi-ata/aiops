import secrets

def new(prefix):
    return f"{prefix}-{secrets.token_hex(8).upper()}"
