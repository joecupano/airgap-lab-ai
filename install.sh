#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PROFILE="${1:-cpu-16gb}"

case "$PROFILE" in
  cpu-16gb) ENV_FILE=".env.cpu-16gb" ;;
  cpu-32gb) ENV_FILE=".env.cpu-32gb" ;;
  cpu-64gb) ENV_FILE=".env.cpu-64gb" ;;
  gpu-6gb-64gb) ENV_FILE=".env.gpu-6gb-64gb" ;;
  template) ENV_FILE=".env.template" ;;
  *)
    echo "Unknown profile: $PROFILE"
    echo "Usage: ./install.sh [cpu-16gb|cpu-32gb|cpu-64gb|gpu-6gb-64gb|template]"
    exit 1
    ;;
esac

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env profile file: $ENV_FILE"
  exit 1
fi

cp "$ENV_FILE" .env
echo "Using profile: $ENV_FILE -> .env"

docker compose up --build -d

echo "Checking API health..."
for attempt in {1..20}; do
  if curl -fsS http://localhost:8000/health >/dev/null; then
    echo "Stack is healthy."
    echo "UI: http://localhost:8080"
    echo "API: http://localhost:8000"
    exit 0
  fi
  sleep 2
done

echo "Health check did not pass yet. Check logs: docker compose logs -f rag-api"
exit 1
