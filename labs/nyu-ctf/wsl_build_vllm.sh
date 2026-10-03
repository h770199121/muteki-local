#!/usr/bin/env bash
set -u
export PATH="/root/.local/bin:/usr/local/cuda-13.0/bin:$PATH"
export CUDA_HOME=/usr/local/cuda-13.0
export ASSUME_YES=1
export MAX_JOBS=6
export ALLOW_HOST_MISMATCH=1   # WSL2 kernel is 6.x; build target expects >=7.
                               # vLLM compiles in userspace — kernel gate is a
                               # runtime-feature check, risk accepted.
cd /opt/build/vLLM-2080Ti-Definitive
exec ./build.sh
