#!/usr/bin/env bash
#
# Generate Python gRPC stubs from trace.proto into the ingestion-server and sdk
# services. Run from anywhere with:  bash proto/generate.sh
#
set -euo pipefail

# Resolve the directory this script lives in (the proto/ dir) and the repo root.
PROTO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${PROTO_DIR}/.." && pwd)"

OUT_DIRS=("${ROOT_DIR}/ingestion-server" "${ROOT_DIR}/sdk")

for OUT_DIR in "${OUT_DIRS[@]}"; do
  echo "Generating stubs into ${OUT_DIR} ..."
  mkdir -p "${OUT_DIR}"
  python3 -m grpc_tools.protoc \
    --proto_path="${PROTO_DIR}" \
    --python_out="${OUT_DIR}" \
    --grpc_python_out="${OUT_DIR}" \
    "${PROTO_DIR}/trace.proto"
done

echo "Done. Generated trace_pb2.py and trace_pb2_grpc.py in: ${OUT_DIRS[*]}"
