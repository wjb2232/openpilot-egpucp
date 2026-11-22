#!/bin/bash
# Build libgpuwarp.so on the vehicle (needs /usr/local/cuda/bin/nvcc).
# sm_87 = Jetson Orin. The .so links cudart shared with an rpath so it shares
# the same libcudart.so.13 instance TensorRT already loaded in the process.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
/usr/local/cuda/bin/nvcc -O3 --cudart=shared -arch=sm_87 -shared -Xcompiler -fPIC \
  "$DIR/warp_kernel.cu" -o "$DIR/libgpuwarp.so" \
  -Xlinker -rpath,/usr/local/cuda/lib64
echo "built $DIR/libgpuwarp.so"
