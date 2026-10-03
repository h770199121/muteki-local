#!/usr/bin/env bash
# Download RedHatAI/Qwen3.8-27B-INT4 (W4A16, vLLM-native) from ModelScope
# (HF is unreachable from this network; modelscope.cn mirror confirmed 200).
# Target: D:\AI\models-hf\Qwen3.8-27B-INT4  (~16-18 GB)
set -eu
DEST="D:/AI/models-hf/Qwen3.8-27B-INT4"
mkdir -p "$DEST"
uv tool run --from modelscope ms download --local_dir "$DEST" RedHatAI/Qwen3.8-27B-INT4 2>&1 | tail -5 || \
python -m pip install modelscope -q && python -m modelscope download --local_dir "$DEST" RedHatAI/Qwen3.8-27B-INT4 2>&1 | tail -5
echo "downloaded to $DEST"
ls -la "$DEST" | head -20
