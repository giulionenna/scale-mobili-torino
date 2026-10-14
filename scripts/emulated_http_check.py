"""Servizi HTTP emulati con Moto e API reale; nessun endpoint AWS contattato."""

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from moto.server import ThreadedMotoServer


def free_port():
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return connection.getsockname()[1]


def main():
    root = Path(__file__).resolve().parents[1]
    data_port, api_port = free_port(), free_port()
    emulator = ThreadedMotoServer(ip_address="127.0.0.1", port=data_port, verbose=False)
    emulator.start()
    # Le credenziali del task non vengono usate né inoltrate dagli emulatori.
    env = {
        **os.environ,
        "AWS_ACCESS_KEY_ID": "local-only",
        "AWS_SECRET_ACCESS_KEY": "local-only",
        "AWS_SESSION_TOKEN": "",
        "AWS_EC2_METADATA_DISABLED": "true",
        "SMT_MODE": "local",
        "SMT_CORE_TABLE": "smt-local-core",
        "SMT_EVENTS_TABLE": "smt-local-events",
        "SMT_PHOTOS_BUCKET": "smt-local-photos",
        "SMT_SOURCES_BUCKET": "smt-local-sources",
        "SMT_DYNAMODB_ENDPOINT": f"http://127.0.0.1:{data_port}",
        "SMT_S3_ENDPOINT": f"http://127.0.0.1:{data_port}",
        "SMT_CURSOR_SECRET": "local-only-cursors-at-least-32-characters",
        "SMT_PUBLIC_URL": f"http://127.0.0.1:{api_port}",
    }
    process = None
    try:
        subprocess.run(
            [
                sys.executable,
                "-c",
                "from scale_mobili.cli import main; main()",
                "bootstrap-local",
            ],
            env=env,
            cwd=root,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-c",
                "from scale_mobili.cli import main; main()",
                "seed",
                "--synthetic",
            ],
            env=env,
            cwd=root,
            check=True,
        )
        with tempfile.TemporaryFile() as log:

            def start():
                return subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "scale_mobili.app:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(api_port),
                        "--no-access-log",
                    ],
                    env=env,
                    cwd=root,
                    stdout=log,
                    stderr=log,
                )

            def ready():
                for _ in range(100):
                    if process.poll() is not None:
                        log.seek(0)
                        raise RuntimeError(log.read().decode()[-2000:])
                    try:
                        if (
                            httpx.get(
                                f"http://127.0.0.1:{api_port}/health", timeout=1
                            ).status_code
                            == 200
                        ):
                            return
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.1)
                raise RuntimeError("Backend non pronto entro il tempo previsto")

            process = start()
            ready()
            subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts/backend_http_smoke.py"),
                    "--url",
                    f"http://127.0.0.1:{api_port}",
                ],
                cwd=root,
                env=env,
                check=True,
            )
            before = httpx.get(
                f"http://127.0.0.1:{api_port}/api/stats/availability"
            ).json()
            process.terminate()
            process.wait(timeout=10)
            process = start()
            ready()
            after = httpx.get(
                f"http://127.0.0.1:{api_port}/api/stats/availability"
            ).json()
            assert before["total"] == after["total"] == 10
            assert httpx.get(f"http://127.0.0.1:{api_port}/api/feed").json()["items"]
            print(
                "HTTP API + DynamoDB/S3 emulati: flussi completi e persistenza tra riavvii API riusciti."
            )
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        emulator.stop()


if __name__ == "__main__":
    main()
