<!-- Example output of hyperresearch-codex 0.3 (2026-09-13). Command: hpr run "What are the practical limits of Apple Silicon unified memory for running local image generation models, and how do GGUF quantizations change them?" --lang en --preset lean --budget 700000. Unedited except this header line. Only source titles and URLs are listed; fetched page text is not included. -->
<!-- hyperresearch-codex light -->
<!-- run: tp-light-en-1 · 출처 8개(독립 묶음 8, 실제 인용 8) · 지적 7개 · 인용표본 5개 중 미지지 1개 · 판단 표시 2개 · 린트 OK · 모델 호출 7회 · 토큰 in 604,783 (캐시 385,024) / out 7,018 · 요금 상한 ≈$6.4 -->
# Question: What are the practical limits of Apple Silicon unified memory for running local image generation models, and how do GGUF quantizations change them?

## Answer

GGUF reduces stored-weight requirements substantially, but complete-pipeline memory—not checkpoint size alone—determines practical feasibility; this is an inference from the documented loading and activation behavior. [S2][S3][S6] Apple Silicon generation remains constrained by memory pressure, swapping, and backend restrictions. [S1] The supplied notes establish neither a safe memory budget for individual Macs nor a guaranteed Apple Silicon speedup from GGUF. [S1][S2][S3]

## Evidence

Diffusers reports that swapping significantly slows M1/M2 inference and recommends attention slicing especially below 64GB RAM or above 512×512 resolution. [S1]

The retained MPS excerpt explicitly states that NDArray sizes greater than `2**32` are unsupported, but does not retain the batch-failure warning or iteration workaround. [S1]

The retained Diffusers example loads a GGUF transformer using `from_single_file` and `GGUFQuantizationConfig`, then passes it into `FluxPipeline`. [S2] Weights remain compressed, typically as `torch.uint8`, and are dequantized into `compute_dtype` during each module’s forward pass. [S2]

For the 12B-parameter FLUX.1-dev, listed files include F16 at 23.8 GB, Q8_0 at 12.7 GB, Q6_K at 9.86 GB, Q5_K_S at 8.29 GB, Q4_K_S at 6.81 GB, Q3_K_S at 5.23 GB, and Q2_K at 4.03 GB. [S3]

ComfyUI-GGUF says transformer/DiT models such as FLUX seem less affected by quantization than convolutional UNET models; it also supports quantized T5 loading for additional memory savings. [S4]

ComfyUI-GGUF describes itself as work in progress, with experimental LoRA support, and reports a Sequoia issue where torch 2.6.X nightlies produce buffer errors while 2.4.1 seems required. [S4]

The retained stable-diffusion.cpp excerpt confirms GGUF, Flash Attention, VAE tiling, and TAESD decoding features, but does not retain the analyst’s explicit Mac OS/Metal support listing. [S5]

Decoding four images together increases peak activation memory fourfold in Diffusers’ example; VAE slicing decodes individually, while tiling processes overlapping image regions to reduce peak memory. [S6]

Diffusers describes whole-model offloading as faster than selectively moving layers or model components, with smaller memory savings. [S6] The retained excerpt discusses group-offloading memory adjustments without preserving the analyst’s complete performance ranking. [S6]

Apple documents 1-, 2-, 4-, 6-, and 8-bit palettization and just-in-time decompression of compressed weights with iOS 17 and macOS 14, reducing memory use; this behavior depends on compute unit, layer type, and hardware generation. [S7]

The retained Apple excerpt does not verify the described `reduceMemory` behavior or latency figures. [S7]

The Core ML article describes six-bit palettization as reducing size and resource use with minimal quality impact, but its retained text does not substantiate the analyst’s macOS-versus-iOS attention-performance comparison. [S8]

The inference is that smaller GGUF files leave more room for generation, while dequantization, text encoders, VAE processing, and activations prevent file size from predicting total runtime memory. [S2][S3][S4][S6]

No retained evidence establishes that GGUF removes the documented MPS array restriction; the approximately 10% acceleration described by Diffusers concerns optimized CUDA kernels. [S1][S2]

## Counter-evidence and limits

The sources offer qualifications rather than direct disagreement: ComfyUI’s favorable quantization assessment is tentative, while Core ML’s quality claims concern a different compression route. [S4][S8] Neither supplies a controlled comparison of the listed FLUX GGUF variants on Apple hardware. [S3][S4][S8]

A measured GPU allocation ceiling, operating-system reserve, and complete-pipeline benchmark matrix for specific Macs remain unavailable. (no source) General offloading guidance does not establish equivalent savings or compatibility on Apple unified memory. [S6] The Apple excerpt is truncated and provides no answer about generation with 8GB RAM. [S7] Consequently, a reliable minimum-RAM purchase recommendation cannot be verified from these notes. (no source)

## Next actions

- Follow Diffusers’ attention-slicing guidance to reduce memory pressure. [S1]
- Benchmark the intended pipeline on the target Mac, recording peak memory, swapping, generation time, and image quality across quantizations. (no source) (judgment)
- Compare GGUF and Core ML using matching generation settings before choosing a runtime. (no source) (judgment)

## Sources

- [S1] Metal Performance Shaders (MPS) — https://huggingface.co/docs/diffusers/main/optimization/mps
- [S2] GGUF | Hugging Face Diffusers — https://huggingface.co/docs/diffusers/quantization/gguf
- [S3] city96/FLUX.1-dev-gguf — https://huggingface.co/city96/FLUX.1-dev-gguf
- [S4] city96/ComfyUI-GGUF — https://github.com/city96/ComfyUI-GGUF
- [S5] leejet/stable-diffusion.cpp — https://github.com/leejet/stable-diffusion.cpp
- [S6] Reduce memory usage | Diffusers — https://github.com/huggingface/diffusers/blob/main/docs/source/en/optimization/memory.md
- [S7] Stable Diffusion with Core ML on Apple Silicon — https://github.com/apple/ml-stable-diffusion
- [S8] Faster Stable Diffusion with Core ML on iPhone, iPad, and Mac — https://huggingface.co/blog/fast-diffusers-coreml
## Source details (auto-generated)

| id | title | domain | published | fetched | cluster | route | cited |
|---|---|---|---|---|---|---|---|
| S1 | Metal Performance Shaders (MPS) | huggingface.co | n/a | 2026-09-13 | S1 | codex_scout (primary) | yes |
| S2 | GGUF   Hugging Face Diffusers | huggingface.co | n/a | 2026-09-13 | S2 | codex_scout (primary) | yes |
| S3 | city96/FLUX.1-dev-gguf | huggingface.co | 2025-05-08 | 2026-09-13 | S3 | codex_scout (primary) | yes |
| S4 | city96/ComfyUI-GGUF | github.com | n/a | 2026-09-13 | S4 | codex_scout (primary) | yes |
| S5 | leejet/stable-diffusion.cpp | github.com | n/a | 2026-09-13 | S5 | codex_scout (primary) | yes |
| S6 | Reduce memory usage   Diffusers | github.com | n/a | 2026-09-13 | S6 | codex_scout (primary) | yes |
| S7 | Stable Diffusion with Core ML on Apple Silicon | github.com | n/a | 2026-09-13 | S7 | codex_scout (primary) | yes |
| S8 | Faster Stable Diffusion with Core ML on iPhone, iPad, and Ma | huggingface.co | 2023-06-15 | 2026-09-13 | S8 | codex_scout (primary) | yes |

\* published date taken from the server's Last-Modified header (may not be the original publication date)

## Sentences flagged by the citation check
- The retained MPS excerpt explicitly states that NDArray sizes greater than `2**32` are unsupported, but does not retain the batch-failure warning or iteration workaround. [S1] → S1 confirms the NDArray limit, but also retains the batch-failure warning and explicitly recommends iterating instead of batching.
