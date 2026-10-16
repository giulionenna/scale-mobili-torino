from hashlib import sha256

ACTIVE_CATALOG = {"PK": "CATALOG#ACTIVE", "SK": "CURRENT"}


def inventory_identity_key(kind: str, official_id: str) -> dict:
    digest = sha256(f"gtt-m1\0{kind}\0{official_id.replace(' ', '')}".encode()).hexdigest()
    return {"PK": f"INVENTORY_ID#{digest}", "SK": "CLAIM"}


def favorite_stations_key(actor_id: str) -> dict:
    return {"PK": f"USER#{actor_id}", "SK": "FAVORITE_STATIONS"}


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
