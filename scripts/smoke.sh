#!/usr/bin/env bash
# Exercise real S6 startup before authentication, without host networking or keys.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
fixture=$(mktemp -d)
container="tailscale-pro-smoke-${RANDOM}"
cleanup() {
  docker logs "${container}" || true
  docker stop -t 15 "${container}" >/dev/null 2>&1 || true
  docker rm -f "${container}" >/dev/null 2>&1 || true
  rm -rf "${fixture}"
}
trap cleanup EXIT
mkdir -p "${fixture}/data" "${fixture}/config"
python3 - "${root}" "${fixture}" <<'PY'
import json,sys
from pathlib import Path
root,fixture=map(Path,sys.argv[1:])
options=json.loads((root/'tailscale_professional/defaults.json').read_text())
options.update(userspace_networking=True,login_server='http://127.0.0.1:9',log_suppression=False)
(fixture/'data/options.json').write_text(json.dumps(options))
PY
docker run -d --name "${container}" --network none \
  --add-host supervisor:127.0.0.1 -e SUPERVISOR_TOKEN=smoke-only \
  -v "${fixture}/data:/data" -v "${fixture}/config:/config" \
  -v "${root}/tests/mock_supervisor.py:/mock_supervisor.py:ro" \
  --entrypoint /bin/bash tailscale-professional:test -ec \
  'python3 /mock_supervisor.py & for i in $(seq 1 30); do curl -sf http://supervisor/info >/dev/null && break; sleep 0.2; done; exec /init'
ready=false
for attempt in $(seq 1 60); do
  if docker exec "${container}" test -s /run/tailscale-professional/port; then
    ready=true; break
  fi
  sleep 1
done
if [[ "${ready}" != true ]]; then echo 'Dashboard failed to start before login'; exit 1; fi
docker exec -i "${container}" python3 - <<'PY'
import json,urllib.request,urllib.error
from pathlib import Path
root=Path('/run/tailscale-professional')
base='http://127.0.0.1:'+root.joinpath('port').read_text()
token=root.joinpath('proxy-token').read_text()
try:
    urllib.request.urlopen(base+'/api/session',timeout=10)
    raise AssertionError('Backend accessible without private proxy token')
except urllib.error.HTTPError as e:
    assert e.code==403
request=urllib.request.Request(base+'/api/session',headers={'X-Professional-Token':token})
with urllib.request.urlopen(request,timeout=15) as response: session=json.load(response)
assert session['settings']['userspace_networking'] is True
assert session['status']['state'] in ('NoState','NeedsLogin','Starting','Stopped','Unavailable')
assert session['csrf'] and not session['has_auth_key']
body=json.dumps({'revision':session['revision'],'settings':{'hostname':'smoke-device'}}).encode()
request=urllib.request.Request(base+'/api/setup',data=body,headers={'X-Professional-Token':token,'X-CSRF-Token':session['csrf'],'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=15) as response: assert json.load(response)['saved']
print('Real S6 startup, pre-login dashboard, private proxy boundary, and Supervisor setup persistence: PASS')
PY
# nginx should reject a request that does not come from the Supervisor gateway.
for attempt in $(seq 1 30); do
  code=$(docker exec "${container}" curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8099/professional/ || true)
  if [[ "${code}" == 403 ]]; then echo 'Ingress gateway restriction: PASS'; exit 0; fi
  sleep 1
done
echo 'nginx ingress did not become ready or failed to restrict non-gateway access'
exit 1
