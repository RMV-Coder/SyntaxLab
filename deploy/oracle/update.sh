#!/usr/bin/env bash
# Deploy the latest main on the VM: pull, rebuild the API image, restart what changed.
#
#   sudo /opt/syntaxlab/deploy/oracle/update.sh
set -euo pipefail

cd "$(dirname "$0")"
git -C ../.. pull --ff-only
docker compose up -d --build
docker image prune -f >/dev/null # drop superseded images (each is about 1.6 GB)

# The API needs a few seconds to load its models after a restart.
for _ in $(seq 1 60); do
  if docker compose exec -T api python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/ready', timeout=4)" \
    2>/dev/null; then
    echo "Ready at $(git -C ../.. rev-parse --short HEAD)"
    exit 0
  fi
  sleep 5
done
echo "The API did not become ready; see: docker compose logs api" >&2
exit 1
