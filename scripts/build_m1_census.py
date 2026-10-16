"""Estrae fatti dai due allegati GTT pubblici, dopo pdftotext -layout.

Gli originali restano nell'archivio privato. Nessuno stato di funzionamento
viene ricavato da un elenco patrimoniale o dall'assenza nel report manutenzioni.
"""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-10-16"
STATIONS = [
    ("FERMI", "Fermi"),
    ("PARADISO", "Paradiso"),
    ("MARCHE", "Marche"),
    ("MASSAUA", "Massaua"),
    ("POZZO STRADA", "Pozzo Strada"),
    ("MONTE GRAPPA", "Monte Grappa"),
    ("RIVOLI", "Rivoli"),
    ("RACCONIGI", "Racconigi"),
    ("BERNINI", "Bernini"),
    ("PRINCIPI D'ACAJA", "Principi d’Acaja"),
    ("XVIII DICEMBRE", "XVIII Dicembre"),
    ("PORTA SUSA", "Porta Susa"),
    ("VINZAGLIO", "Vinzaglio"),
    ("RE UMBERTO", "Re Umberto"),
    ("PORTA NUOVA", "Porta Nuova"),
    ("MARCONI", "Marconi"),
    ("NIZZA", "Nizza"),
    ("DANTE", "Dante"),
    ("CARDUCCI", "Carducci-Molinette"),
    ("SPEZIA", "Spezia"),
    ("LINGOTTO", "Lingotto"),
    ("ITALIA 61", "Italia ’61–Regione Piemonte"),
    ("BENGASI", "Bengasi"),
]
ROUTES = {
    "banch/atrio": "Banchina ↔ atrio",
    "banch/mezz": "Banchina ↔ mezzanino",
    "mezzan/atrio": "Mezzanino ↔ atrio",
    "atrio/esterno": "Atrio ↔ esterno",
}


def identifier(value):
    # Assegnazione iniziale: gli ID pubblicati si conservano nelle revisioni future.
    return str(
        uuid5(NAMESPACE_URL, "https://scale-mobili-torino.invalid/catalog/" + value)
    )


def source(root, tender, filename, zip_name, url, label, published_at):
    document = root / f"tender-{tender}-files" / filename
    archive = root / zip_name
    return {
        "source_id": f"gtt-pa-{tender}-allegato-2",
        "title": label,
        "publisher": "GTT",
        "url": f"https://gtt-to.acquistitelematici.it/tender/{tender}",
        "download_url": url,
        "document": filename,
        "document_sha256": hashlib.sha256(document.read_bytes()).hexdigest(),
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "published_at": published_at,
        "acquired_at": datetime.fromtimestamp(archive.stat().st_mtime, UTC).isoformat(),
    }


def build(evidence_root):
    sources = [
        source(
            evidence_root,
            7773,
            "Allegato 2 Elenco Impianti.pdf",
            "tender-7773-capitolato.zip",
            "https://gtt-to.acquistitelematici.it/tender/documenti/13772/"
            "Allegati+al+Capitolato.zip?dmsDoc=1",
            "PA 58/2026 · Allegato 2B · Scale mobili",
            "2026-03-31T14:35:40Z",
        ),
        source(
            evidence_root,
            5133,
            "All_2_Manutenzione_ascensori.pdf",
            "tender-5133-capitolato.zip",
            "https://gtt-to.acquistitelematici.it/tender/documenti/3613/"
            "82.25_Capitolato.zip?dmsDoc=1",
            "PA 82/2025 · Allegato 2 · Ascensori (revisione 21 marzo 2025)",
            "2025-04-28T14:39:24Z",
        ),
    ]
    stations = [
        {
            "station_id": identifier("station/" + raw),
            "name": name,
            "line": "M1",
            "line_order": index,
            "synthetic": False,
            "source_url": (
                "https://www.gtt.to.it/cms/percorari/urbano?bacino=U&linea=METRO"
                "&palina=8232&realtime=true&view=palina"
                if raw == "ITALIA 61"
                else "https://www.gtt.to.it/cms/linee-e-orari/torino-e-cintura/"
                "urbana/240-metropolitana.html"
            ),
        }
        for index, (raw, name) in enumerate(STATIONS, 1)
    ]
    station_ids = {
        raw: station["station_id"] for (raw, _), station in zip(STATIONS, stations)
    }
    devices = []
    patterns = [
        (
            "scala_mobile",
            "scale-elenco-2026.txt",
            re.compile(
                r"^\s*(.+?)\s{2,}([A-Z0-9]+(?: [0-9]+)?)\s+"
                r"(banch/atrio|atrio/esterno|mezzan/atrio|banch/mezz)\s+"
                r"(\d+)\s+(\d+)\s+(salita|discesa)\s+(\d{4})\s+(Schindler|Otis)\s*$"
            ),
        ),
        (
            "ascensore",
            "ascensori-elenco-2025.txt",
            re.compile(
                r"^\s*(.+?)\s{2,}([A-Z0-9]+(?:-\d+)?)\s+"
                r"(Atrio/Esterno|Banchina/\s*Atrio)\s+(\d{4})\s+"
                r'(Oleodinamico|elettrico "roomless")\s+(Schindler|Otis)\s*\(([^)]+)\)\s*$'
            ),
        ),
    ]
    for source_index, (kind, text_name, pattern) in enumerate(patterns):
        evidence = sources[source_index]
        for page, content in enumerate(
            (evidence_root / text_name).read_text().split("\f"), 1
        ):
            for line in content.splitlines():
                match = pattern.match(line)
                if not match:
                    # Non ignorare in silenzio righe di impianti che non si riescono a leggere.
                    if re.match(r"^\s*[A-Z][A-Z ' .0-9]+\s{2,}\w+\s+\S*/", line):
                        raise ValueError(
                            f"Riga non interpretata, pagina {page}: {line}"
                        )
                    continue
                values = match.groups()
                raw_station, raw_id, route = values[:3]
                raw_station = raw_station.strip()
                station_id = station_ids[
                    raw_station.replace("PORTA. NUOVA", "PORTA NUOVA")
                ]
                official_id = raw_id.strip()
                if kind == "scala_mobile":
                    height, steps, direction, year, manufacturer = values[3:]
                    technical = {
                        "rise_mm": int(height),
                        "steps": int(steps),
                        "planned_direction": direction,
                    }
                    location = ROUTES[route] + " · " + direction + " prevista"
                else:
                    year, drive, manufacturer, _note = values[3:]
                    technical = {"drive": drive}
                    location = (
                        "Atrio ↔ esterno"
                        if route == "Atrio/Esterno"
                        else "Banchina ↔ atrio"
                    )
                devices.append(
                    {
                        "device_id": identifier(
                            kind + "/" + official_id.replace(" ", "")
                        ),
                        "station_id": station_id,
                        "name": f"{'Scala mobile' if kind == 'scala_mobile' else 'Ascensore'} "
                        f"· {official_id}",
                        "kind": kind,
                        "location": location,
                        "official_id": official_id,
                        "operator": None,
                        "manufacturer": manufacturer,
                        "commissioning_year": int(year),
                        "technical": technical,
                        "synthetic": False,
                        "inventory_evidence": {
                            **evidence,
                            "page": page,
                            "station_label": raw_station,
                            "position_label": route,
                            "verification": "documentary_inventory",
                            "on_site_verified": False,
                            "identification_note": (
                                "Matricola RL10924 riportata così nel documento; "
                                "sequenza numerica atipica da verificare sulla targhetta."
                                if official_id == "RL10924"
                                else "Uscita e direzione della banchina da verificare sul posto."
                            ),
                        },
                    }
                )
    counts = Counter(d["kind"] for d in devices)
    assert counts == {"scala_mobile": 142, "ascensore": 73}, counts
    assert len({d["device_id"] for d in devices}) == 215
    assert len({(d["kind"], d["official_id"].replace(" ", "")) for d in devices}) == 215
    assert {d["station_id"] for d in devices} == set(station_ids.values())
    dataset = {
        "schema_version": 1,
        "dataset_id": f"torino-m1-{DATE}",
        "researched_at": DATE,
        "scope": "M1 passeggeri, tratta in esercizio Fermi–Bengasi; perimetro allegati GTT",
        "status_included": False,
        "sources": sources,
        "cross_check": {
            "url": "https://www.gtt.to.it/cms/en/19-linee-e-orari/urbana/"
            "12186-metropolitana-aggiornamento-ascensori-e-scale-mobili",
            "chart_date": DATE,
            "escalators": 142,
            "lifts": 73,
            "meaning": "Riscontro dei totali; nessuna associazione automatica degli stati.",
        },
        "exclusions": [
            "7 ascensori del comprensorio tecnico di Collegno (allegato ascensori, pagina 3)",
            "Impianti ferroviari e collegamenti di Grandi Stazioni fuori dal perimetro GTT",
            "Estensioni e stazioni non ancora in esercizio",
        ],
        "limitations": [
            "Censimento documentale, non sopralluogo né certificazione dello stato attuale.",
            "Matricole trascritte dal campo Matricola, inclusi i suffissi presenti nel documento.",
            "Nessuna attribuzione di banchina Fermi/Bengasi o uscita stradale senza prova.",
            "Dati tecnici indicativi come specificato dall'allegato; gestore non attribuito.",
        ],
        "stations": stations,
        "devices": devices,
    }
    path = ROOT / "data" / f"{dataset['dataset_id']}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n")
    csv_path = ROOT / "frontend/static/censimento-m1.csv"
    csv_path.parent.mkdir(exist_ok=True)
    names = {s["station_id"]: s["name"] for s in stations}
    with csv_path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "stazione",
                "tipo",
                "matricola_documento",
                "collegamento",
                "costruttore",
                "anno_messa_esercizio",
                "id_interno",
                "fonte",
                "documento",
                "pagina",
                "sha256",
            ]
        )
        for device in devices:
            evidence = device["inventory_evidence"]
            writer.writerow(
                [
                    names[device["station_id"]],
                    device["kind"],
                    device["official_id"],
                    device["location"],
                    device["manufacturer"],
                    device["commissioning_year"],
                    device["device_id"],
                    evidence["url"],
                    evidence["document"],
                    evidence["page"],
                    evidence["document_sha256"],
                ]
            )
    print(
        json.dumps(
            {"stations": len(stations), "devices": len(devices), "counts": counts}
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_root", type=Path)
    build(parser.parse_args().evidence_root)
