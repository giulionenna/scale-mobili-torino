from hashlib import sha256


def escalator(escalator_id: str) -> str:
    return f"ESC#{escalator_id}"


def event_key(event: dict) -> dict:
    return {
        "PK": escalator(event["escalator_id"]),
        "SK": f"EVENT#{event['recorded_at']}#{event['event_id']}",
    }


def idempotency_key(actor_id: str, request_key: str) -> dict:
    digest = sha256(f"{actor_id}\0{request_key}".encode()).hexdigest()
    return {"PK": f"IDEMP#{digest}", "SK": "WRITE"}
