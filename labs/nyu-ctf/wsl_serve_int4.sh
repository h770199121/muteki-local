#!/usr/bin/env bash
# vLLM serve: Qwen3.8-27B INT4 (W4A16) TP=2 on 2080+T10, MTP K=3.
cd /opt/build/vLLM-2080Ti-Definitive
exec ./.venv/bin/vllm serve /mnt/d/AI/models-hf/Qwen3.8-27B-INT4 \
  --served-model-name qwen3.8-27b-int4 \
  --tensor-parallel-size 2 \
  --quantization compressed-tensors \
  --kv-cache-dtype fp8 \
  --max-model-len 131072 \
  --gpu-memory-utilization 0.85 \
  --max-num-seqs 1 \
  --speculative-config '{"method":"mtp","num_speculative_tokens":3}' \
  --port 18220
