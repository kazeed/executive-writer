#!/usr/bin/env bash
set -euo pipefail
container=$(docker run -d --read-only --cap-drop=ALL --security-opt=no-new-privileges --memory=256m --cpus=1 --pids-limit=64 -p 127.0.0.1::8000 executive-writer:local)
trap 'docker logs "$container"; docker rm -f "$container" >/dev/null' EXIT
port=$(docker port "$container" 8000/tcp | cut -d: -f2)
for attempt in {1..30}; do
  if curl --fail --silent "http://127.0.0.1:$port/health" > /tmp/ew-health.json; then break; fi
  sleep 1
done
python3 -c 'import json; assert json.load(open("/tmp/ew-health.json")) == {"status": "ok"}'
response=$(curl --fail --silent -o /tmp/ew-document.json -w '%{http_code}' -H 'Content-Type: application/json' -d '{"objective":"Smoke test","document_type":"memo"}' "http://127.0.0.1:$port/documents")
test "$response" = 202
python3 -c 'import json,uuid; d=json.load(open("/tmp/ew-document.json")); assert d["status"] == "accepted" and d["document_type"] == "memo"; assert uuid.UUID(d["document_id"]).version == 4'
for path in docs openapi.json; do curl --fail --silent "http://127.0.0.1:$port/$path" >/dev/null; done
docker exec "$container" python -c 'import os; assert os.getuid() == 10001'
for attempt in {1..45}; do
  health=$(docker inspect -f '{{.State.Health.Status}}' "$container")
  if test "$health" = healthy; then break; fi
  sleep 1
done
test "$health" = healthy
docker stop --time 15 "$container" >/dev/null
test "$(docker inspect -f '{{.State.ExitCode}}' "$container")" = 0
