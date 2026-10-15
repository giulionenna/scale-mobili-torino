"""Bundle Python 3.12/x86_64 da uv.lock, senza credenziali o dati applicativi."""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


def build(destination):
    root = Path(__file__).resolve().parents[1]
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("Installare la versione uv indicata dalla CI")
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="smt-lambda-") as temporary:
        folder = Path(temporary)
        requirements = folder / "requirements.txt"
        subprocess.run(
            [
                uv,
                "export",
                "--project",
                str(root / "backend"),
                "--frozen",
                "--no-dev",
                "--no-emit-project",
                "--output-file",
                str(requirements),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        target = folder / "bundle"
        subprocess.run(
            [
                uv,
                "pip",
                "install",
                "--python-version",
                "3.12",
                "--python-platform",
                "x86_64-manylinux_2_28",
                "--only-binary",
                ":all:",
                "--require-hashes",
                "--target",
                str(target),
                "--requirements",
                str(requirements),
            ],
            check=True,
        )
        shutil.copytree(
            root / "backend/src/scale_mobili",
            target / "scale_mobili",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        provenance = {
            "python": "3.12",
            "architecture": "x86_64",
            "lock_sha256": hashlib.sha256(
                (root / "backend/uv.lock").read_bytes()
            ).hexdigest(),
        }
        (target / "build-info.json").write_text(json.dumps(provenance, sort_keys=True))
        with zipfile.ZipFile(
            destination, "w", zipfile.ZIP_DEFLATED, compresslevel=6
        ) as archive:
            for path in sorted(target.rglob("*")):
                if (
                    path.is_file()
                    and "__pycache__" not in path.parts
                    and path.suffix != ".pyc"
                ):
                    info = zipfile.ZipInfo(
                        str(path.relative_to(target)), date_time=(2026, 1, 1, 0, 0, 0)
                    )
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o644 << 16
                    archive.writestr(info, path.read_bytes())
        if destination.stat().st_size > 50 * 1024 * 1024:
            raise RuntimeError("Bundle oltre il limite dell'upload diretto Lambda")
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    print(
        json.dumps(
            {
                "archive": str(destination),
                "sha256": digest,
                "size_bytes": destination.stat().st_size,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("dist/backend-lambda.zip"))
    build(parser.parse_args().output)
