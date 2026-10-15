"""Lega piano e bundle al commit verificato prima dell'apply manuale."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["write", "verify"])
    parser.add_argument("--commit", required=True)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    arguments = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", arguments.commit):
        raise ValueError("Commit SHA non valido")
    data = {
        "commit_sha": arguments.commit,
        "plan_sha256": digest(arguments.plan),
        "bundle_sha256": digest(arguments.bundle),
        "schema_version": 1,
    }
    if arguments.action == "write":
        arguments.manifest.write_text(json.dumps(data, indent=2) + "\n")
    elif json.loads(arguments.manifest.read_text()) != data:
        raise ValueError("Piano, bundle o commit differiscono da quelli revisionati")
    print(f"Provenienza {arguments.action} verificata per {arguments.commit}.")


if __name__ == "__main__":
    main()
