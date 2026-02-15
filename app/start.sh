#!/usr/bin/env bash
set -e

mkdir -p "${VECTOR_STORE_PATH:-/workspace/index}"
mkdir -p "${CORPUS_PATH:-${RF_CORPUS_PATH:-/workspace/data/corpus}}"

exec uvicorn src.main:app --host 0.0.0.0 --port 8000
