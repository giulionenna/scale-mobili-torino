"""Importa ed esegue il bundle isolato, senza site-packages o servizi AWS."""

import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

archive = Path("dist/backend-lambda.zip").resolve()
with tempfile.TemporaryDirectory(prefix="smt-lambda-check-") as temporary:
    with zipfile.ZipFile(archive) as bundle:
        files = bundle.namelist()
        assert "scale_mobili/app.py" in files and "scale_mobili/workers.py" in files
        assert "PIL/Image.py" in files
        assert not any(
            part in {".env", ".git", ".aws", "private-data", "private-photos"}
            for filename in files
            for part in Path(filename).parts
        )
        bundle.extractall(temporary)
    env = {
        **os.environ,
        "PYTHONPATH": temporary,
        "SMT_MODE": "demo",
        "AWS_EC2_METADATA_DISABLED": "true",
    }
    program = """
import json
from scale_mobili.app import handler
event = {'version':'2.0','routeKey':'$default','rawPath':'/api/stats/availability',
 'rawQueryString':'','headers':{'host':'localhost:8000'},
 'requestContext':{'http':{'method':'GET','path':'/api/stats/availability',
 'sourceIp':'127.0.0.1','protocol':'HTTP/1.1'}},'body':'','isBase64Encoded':False}
for _ in range(2):
 response=handler(event,{})
 assert response['statusCode']==200, response
 body=json.loads(response['body'])
 assert body['total']==9 and body['percentage']==0 and body['continuous_availability'] is False
print('Bundle Lambda isolato: import e invocazioni ripetute riusciti, 9 impianti sintetici.')
"""
    subprocess.run(
        [sys.executable, "-S", "-c", program], cwd=temporary, env=env, check=True
    )
