// GPU warp for modeld: NV12 camera frame -> 6-plane [Y00,Y10,Y01,Y11,U,V]
// model input (each plane 128x256), replacing cv2.warpPerspective on the CPU.
//
// Numerics mirror the CPU path (TrtModelState._warp):
//   - Y planes: perspective warp of the full luma plane, sampled at model
//     coords x_m = 2*c + (p>>1), y_m = 2*r + (p&1) through the inverse matrix.
//   - U/V planes: warp of the interleaved chroma plane with the OpenCV chroma
//     adjustment matrix (M_inv scaled by [[1,1,.5],[1,1,.5],[2,2,1]]).
//   - bilinear interpolation, constant-0 border (cv2 BORDER_CONSTANT).
// Fixed-point quantization inside OpenCV (1/32 px) means results may differ by
// +/-1 LSB per pixel; the driving model is insensitive to that.
//
// Everything runs inside the TrtRunner CUDA context (caller pushes it), so the
// kernel writes directly into the engine's new_img device buffer and the
// per-frame H2D of the warped input disappears along with the CPU warp work.

#include <cuda_runtime.h>

struct Mat3 {  // row-major 3x3: p.x = m[0]x+m[1]y+m[2], p.y = m[3..5], p.z = m[6..8]
  float m[9];
};

__device__ __forceinline__ float bilinear_u8(const unsigned char* src, int stride,
                                             int w, int h, float x, float y) {
  int x0 = (int)floorf(x), y0 = (int)floorf(y);
  float fx = x - (float)x0, fy = y - (float)y0;
  int x1 = x0 + 1, y1 = y0 + 1;
  float v00 = (x0 >= 0 && x0 < w && y0 >= 0 && y0 < h) ? (float)src[y0 * stride + x0] : 0.f;
  float v10 = (x1 >= 0 && x1 < w && y0 >= 0 && y0 < h) ? (float)src[y0 * stride + x1] : 0.f;
  float v01 = (x0 >= 0 && x0 < w && y1 >= 0 && y1 < h) ? (float)src[y1 * stride + x0] : 0.f;
  float v11 = (x1 >= 0 && x1 < w && y1 >= 0 && y1 < h) ? (float)src[y1 * stride + x1] : 0.f;
  return (1.f - fx) * (1.f - fy) * v00 + fx * (1.f - fy) * v10 +
         (1.f - fx) * fy * v01 + fx * fy * v11;
}

// interleaved NV12 chroma plane, logical pixel (x, y) -> bytes 2x (+ch)
__device__ __forceinline__ float bilinear_uv(const unsigned char* uv, int stride,
                                             int w, int h, int ch, float x, float y) {
  int x0 = (int)floorf(x), y0 = (int)floorf(y);
  float fx = x - (float)x0, fy = y - (float)y0;
  int x1 = x0 + 1, y1 = y0 + 1;
  float v00 = (x0 >= 0 && x0 < w && y0 >= 0 && y0 < h) ? (float)uv[y0 * stride + 2 * x0 + ch] : 0.f;
  float v10 = (x1 >= 0 && x1 < w && y0 >= 0 && y0 < h) ? (float)uv[y0 * stride + 2 * x1 + ch] : 0.f;
  float v01 = (x0 >= 0 && x0 < w && y1 >= 0 && y1 < h) ? (float)uv[y1 * stride + 2 * x0 + ch] : 0.f;
  float v11 = (x1 >= 0 && x1 < w && y1 >= 0 && y1 < h) ? (float)uv[y1 * stride + 2 * x1 + ch] : 0.f;
  return (1.f - fx) * (1.f - fy) * v00 + fx * (1.f - fy) * v10 +
         (1.f - fx) * fy * v01 + fx * fy * v11;
}

__device__ __forceinline__ unsigned char pack_u8(float v) {
  int i = (int)lrintf(v);
  return (unsigned char)(i < 0 ? 0 : (i > 255 ? 255 : i));
}

// one thread per plane pixel: blockIdx.z = plane (0..3), each plane covers the
// full model extent -> model coords x_m = 2*c + (p>>1), y_m = 2*r + (p&1)
// [Y00 even/even, Y10 odd/even, Y01 even/odd, Y11 odd/odd, matching the CPU
//  out[p] = ys[...] subsampling]
__global__ void warp_y4_kernel(const unsigned char* nv12, int stride, int uv_offset,
                               int src_w, int src_h, Mat3 minv,
                               unsigned char* out, int out_base, int out_w, int out_h) {
  int c = blockIdx.x * blockDim.x + threadIdx.x;
  int r = blockIdx.y * blockDim.y + threadIdx.y;
  int p = blockIdx.z;
  if (c >= out_w || r >= out_h || p >= 4) return;
  float x_m = 2.f * c + (float)(p >> 1);
  float y_m = 2.f * r + (float)(p & 1);
  float px = minv.m[0] * x_m + minv.m[1] * y_m + minv.m[2];
  float py = minv.m[3] * x_m + minv.m[4] * y_m + minv.m[5];
  float pz = minv.m[6] * x_m + minv.m[7] * y_m + minv.m[8];
  float u = px / pz, v = py / pz;
  out[out_base + (size_t)p * out_w * out_h + r * out_w + c] =
      pack_u8(bilinear_u8(nv12, stride, src_w, src_h, u, v));
}

// one thread per output pixel (r, c) -> writes planes 4(U) and 5(V)
__global__ void warp_uv2_kernel(const unsigned char* nv12, int stride, int uv_offset,
                                int src_w, Mat3 muv,
                                unsigned char* out, int out_base, int out_w, int out_h) {
  int c = blockIdx.x * blockDim.x + threadIdx.x;
  int r = blockIdx.y * blockDim.y + threadIdx.y;
  if (c >= out_w || r >= out_h) return;
  int uv_h = (uv_offset / stride) / 2;  // chroma rows
  float px = muv.m[0] * c + muv.m[1] * r + muv.m[2];
  float py = muv.m[3] * c + muv.m[4] * r + muv.m[5];
  float pz = muv.m[6] * c + muv.m[7] * r + muv.m[8];
  float u = px / pz, v = py / pz;
  const unsigned char* uv = nv12 + uv_offset;
  size_t base = out_base + (size_t)r * out_w + c;
  out[base] = pack_u8(bilinear_uv(uv, stride, src_w / 2, uv_h, 0, u, v));
  out[base + (size_t)out_w * out_h] = pack_u8(bilinear_uv(uv, stride, src_w / 2, uv_h, 1, u, v));
}

extern "C" {

// upload one NV12 frame to a device staging buffer (caller provides buffer)
int gpuw_upload(unsigned char* dst_dev, const unsigned char* src_host, int nbytes) {
  cudaError_t e = cudaMemcpy(dst_dev, src_host, (size_t)nbytes, cudaMemcpyHostToDevice);
  return (int)e;
}

// planes 0..3 for one camera; matrices passed by value (host floats)
int gpuw_y4(const unsigned char* src_dev, int stride, int uv_offset, int src_w, int src_h,
            Mat3 minv, unsigned char* out_dev, int out_base, int out_w, int out_h) {
  dim3 block(16, 16);
  dim3 grid((out_w + 15) / 16, (out_h + 15) / 16, 4);
  warp_y4_kernel<<<grid, block>>>(src_dev, stride, uv_offset, src_w, src_h, minv,
                                  out_dev, out_base, out_w, out_h);
  return (int)cudaGetLastError();
}

// planes 4(U),5(V) for one camera
int gpuw_uv2(const unsigned char* src_dev, int stride, int uv_offset, int src_w,
             Mat3 muv, unsigned char* out_dev, int out_base, int out_w, int out_h) {
  dim3 block(16, 16);
  dim3 grid((out_w + 15) / 16, (out_h + 15) / 16);
  warp_uv2_kernel<<<grid, block>>>(src_dev, stride, uv_offset, src_w, muv,
                                   out_dev, out_base, out_w, out_h);
  return (int)cudaGetLastError();
}

int gpuw_sync(void) { return (int)cudaDeviceSynchronize(); }

}  // extern "C"
