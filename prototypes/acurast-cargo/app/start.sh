#!/bin/sh
set -eu

APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
INPUT_FILE="${FOG_TASK_INPUT:-$APP_DIR/fog_task_payload.json}"
OUTPUT_FILE="${FOG_TASK_OUTPUT:-$APP_DIR/fog_task_result.json}"

python3 "$APP_DIR/fog_task_runner.py" --input "$INPUT_FILE" --output "$OUTPUT_FILE"
cat "$OUTPUT_FILE"
