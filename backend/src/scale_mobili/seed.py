from scale_mobili.domain import DomainError
from scale_mobili.platform import entity
from scale_mobili.repository import record


def seed_synthetic(store):
    """Seed idempotente: quattro stazioni e nove impianti esplicitamente fittizi."""
    created = 0
    for number in range(4):
        station_id = "demo-station" if number == 0 else f"demo-station-{number + 1}"
        station = record(
            {"PK": "CATALOG#STATIONS", "SK": "STATION#" + station_id},
            station_id=station_id,
            name="Stazione fittizia" if number == 0 else f"Stazione fittizia {number + 1}",
            synthetic=True,
            version=1,
        )
        items = [station]
        for position, kind in enumerate(
            ["scala_mobile", "ascensore", *(["scala_mobile"] if number == 0 else [])]
        ):
            device_id = (
                f"demo-esc-{position + 1}"
                if number == 0
                else f"demo-device-{number + 1}-{position + 1}"
            )
            items.append(
                record(
                    entity("ESC", device_id),
                    escalator_id=device_id,
                    station_id=station_id,
                    name=(
                        f"{'Ascensore' if kind == 'ascensore' else 'Scala mobile'} "
                        f"fittizio {position + 1}"
                    ),
                    kind=kind,
                    location="Percorso sintetico, non riferito a un impianto reale",
                    synthetic=True,
                    confirmed=True,
                    version=1,
                    official_id=None,
                    operator=None,
                    station_pk="STATION#" + station_id,
                    station_sk="ESC#" + device_id,
                )
            )
        for item in items:
            previous = store.get_core({"PK": item["PK"], "SK": item["SK"]})
            if previous:
                if not previous.get("synthetic"):
                    raise DomainError("Il seed non può sovrascrivere un record reale", 409)
                continue
            store.transact([(item, 0)])
            created += 1
    return {"created": created, "synthetic": True}
