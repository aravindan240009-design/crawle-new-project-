# Start only the local project search sidecar; preserve certificate verification.
$ErrorActionPreference = 'Stop'
$radarRoot = Split-Path $PSScriptRoot -Parent
Set-Location $radarRoot
$radarCertDir = Join-Path $radarRoot 'data\host-ca'
New-Item -ItemType Directory -Path $radarCertDir -Force | Out-Null
@'
import ssl
from pathlib import Path
folder = Path('data/host-ca')
for n, (cert, encoding, trust) in enumerate(ssl.enum_certificates('ROOT')):
    if encoding == 'x509_asn' and (trust is True or '1.3.6.1.5.5.7.3.1' in trust):
        (folder / f'host-root-{n}.crt').write_text(ssl.DER_cert_to_PEM_cert(cert), encoding='ascii')
'@ | & .\.venv\Scripts\python.exe -
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare existing Windows certificate trust for the container' }
$env:SEARXNG_SECRET = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
docker compose up -d --quiet-pull
if ($LASTEXITCODE -ne 0) { throw 'Docker engine must be running. No search success is assumed.' }
Write-Output 'Local SearXNG started at http://127.0.0.1:8088. Validate engines in a discovery campaign.'
