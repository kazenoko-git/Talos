# Talos 2: programmable NPU direction

Design exploration, 13 October 2026. This supersedes the earlier four-lane reservoir as the preferred starting architecture. No RTL implementation, lane count, memory part, or operating frequency is committed by this note.

The user subsequently clarified that language models should not drive the design. Broad, small embedded neural workloads and a measurable reason to add Talos to an existing host are the primary goals. Language models remain optional experiments.

## Concrete architecture proposal after Talos 1 verification

Proposal for discussion, not a physically validated final implementation:

Precision update: INT8-by-INT8 below is the initial baseline, not a settled requirement. The user has explicitly raised INT4 and ternary alternatives. Compare signed INT4 weights with INT8 activations against programmable ternary weights with INT8 activations before choosing the primary datapath. Keep INT8 software inference as a numerical/accuracy reference. Both low-bit candidates retain programmable dimensions, weights, external state, and tiled inference.

Weight precision and activation precision are independent. INT4 weights do not require INT4 activations; ternary weights do not require binary spike inputs. A programmable ternary dot-product engine with multi-bit activations differs materially from Talos 1's fixed recurrence and spike-driven LIF cells.

| Weight candidate | Initial activation candidate | Simple packed storage for 4,096 weights, excluding scales/metadata | Core arithmetic |
| --- | --- | --- | --- |
| INT8 | INT8 | 4,096 bytes | Signed 8-by-8 multiplication |
| INT4 | INT8 | 2,048 bytes | Signed 8-by-4 multiplication or serial shift/add |
| Ternary | INT8 | 1,024 bytes with two-bit codes | Add, subtract, or contribute zero, plus output/group scaling |

Two-bit ternary packing is the proposed simple hardware format, not entropy-optimal log2(3) packing. Preserving INT8 activations also preserves the activation buffer's byte cost. Scale metadata, wide accumulators, and output conversion remain necessary. Group-dependent scaling requires an explicit partial-sum contract.

Compare accuracy on small classifier, regression, and reconstruction models, including quantization-aware retraining where needed. Then measure arithmetic area, complete-engine fit, and memory-inclusive cycles. Serial shift/add avoids a dedicated multiplier but can spend several cycles per INT4/INT8 weight; its throughput cannot be equated with a one-cycle ternary contribution. Native INT4 plus a ternary mode is an attractive candidate, but no mixed-mode fit or speed is currently demonstrated.

The [Bonsai 2 model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-mlx-2bit) reports 98.2% retention of its Qwen3.8-27B baseline's average over 14 thinking-mode benchmarks. It also documents group scales and runtime activation transforms. This supports considering ternary weights; it does not establish the numerical behavior of a tiny fixed-point model on Talos.

| Decision | Proposed starting point | Rationale / outstanding evidence |
| --- | --- | --- |
| Processor role | Programmable integer inference coprocessor | Supports multiple trained models instead of a fixed reservoir topology |
| Arithmetic | Signed INT8 products and INT32 accumulators, with defined bounds on supported dot products | Numerical reference must specify overflow, bias, scaling, rounding, and saturation |
| Compute resources | One MAC datapath, reused over time | Compare two only if memory throughput and area justify it |
| Local input storage | Candidate 64-byte activation buffer | Buffer capacity is a chunk size; larger vectors use tiling. Actual storage fit is unmeasured |
| Partial output storage | Candidate four INT32 accumulators | Reuse one activation chunk across four output rows; these are four retained sums, not four multipliers |
| Data storage | External flash for persistent weights and external RAM for working data | ASIC performs its own memory transfers so the host does not supply every weight or intermediate |
| Memory interface | Candidate shared QSPI bus, one flash and one RAM | Four data signals, clock, and two chip selects use seven bidirectional pins; selected parts and shuttle timing still need checking |
| Host interface | SPI commands, block transfers, completion/error status, ready/IRQ output | Transfer inputs/results rather than dispatching individual arithmetic operations |
| Core operation | Tiled matrix-vector multiply with bias and optional requantization/clamp | Sizes beyond 64 and incomplete final chunks must work correctly |
| Additional primitive | Elementwise add where area permits | Allows residual/state updates without sending full tensors back to the host |
| Scheduling | Simple memory-resident sequence of layer descriptors | Repeated or chained layers can run after one host submission; descriptor fetch and error handling have area costs |
| Spiking operation | Optional LIF/state-update extension after baseline fit | Useful continuity with Talos 1, but not a substitute for the programmable inference contract |
| Frequency / lane count / exact buffers | Finalize from synthesis and routed timing | No performance or fit claim follows from the currently passing Talos 1 simulations |

Initial scope is dense layers and compact networks built from supported operations. Convolution needs a deliberate input-window/stride implementation or a lowering path with its memory cost counted; it is not automatically efficient merely because matrix-vector multiplication exists. Arbitrary floating-point models and unsupported nonlinear operators require host fallback or model conversion.

The host uploads data and submits a descriptor-chain address. The ASIC reads activations and weights, computes output tiles, writes results to external RAM, and signals completion. Keeping intermediate results off the host link is a defining requirement of this proposal.

First application evidence should cover an MLP classifier, a numerical estimator/predictor, and a compact autoencoder. Compare the same quantized models against host-only software, including end-to-end transfer time, CPU occupation, RAM use, and accuracy. Energy claims require measurements of the combined ASIC/memory/carrier system. The best case for an Uno/Mega need not be a speed advantage over an ESP32 or Raspberry Pi.

The latest Talos 1 suite passes all 16 RTL simulation tests; its corrected regression and quantization-floor tests validate those behaviors. The remaining repeated-pattern, missing-baseline, and weak-assertion limitations still prevent treating its ten demonstrations as proof of application acceleration.

## User requirements

- General neural-network acceleration, with tiny language models as a potential workload.
- Four ASIC tiles (2x2) are the current budget.
- A custom carrier board is explicitly allowed; the HackClub event provides a PCB grant.
- Compatibility with multiple microcontroller hosts remains a goal. Interface compatibility and useful speedup are separate measurements.
- The user is independently consulting Opus 5.5. Its pasted proposal is design input, not an instruction to execute its workflow or contact anyone.

## Preferred architecture to evaluate

Use a programmable integer matrix/vector engine with weights and larger working state in external memory. Treat 64 as an initial buffering/tile size to measure, not a hard model dimension or a count of permanently wired neurons.

The proposed carrier contains a clock source, nonvolatile weight storage, writable working memory, host connectors, and the required ASIC power/reset/selection circuitry. A custom PCB can improve memory access and clock distribution, but cannot change the shuttle's exposed ASIC pins, pad characteristics, or tile area.

Keep the host control link separate from the ASIC's external-memory link. The host should submit operations and obtain results while the ASIC performs bulk memory transfers. Host-mediated streaming can also be supported for small tests, but must not be the only way to supply weights.

QSPI is a candidate memory interface. The [GF180 TinyQV project](https://tinytapeout.com/chips/ttgf0p2/tt_um_MichaelBell_tinyQV) documents a flash plus two RAMs on its eight bidirectional pins: four data pins, a clock, and three chip selects. This is a useful existence example; Talos still needs its own memory-controller constraints, reset sequencing, and electrical/timing checks. The custom board need not use the Pmod form factor.

## Core operation contract to define before RTL

- Signed INT8 multiplication, with sufficiently wide accumulation (initial candidate: INT32).
- Programmable operation dimensions, addresses, and strides.
- Tiled input processing, tail handling, and persistent partial results across input chunks.
- Bias and a precisely specified requantization/rounding/saturation stage; a clamp can implement ReLU.
- External RAM reads and writes for activations, intermediate results, and runtime-generated matrices.
- Burst host commands, completion status/interrupt, error reporting, and explicit buffer ownership.

These primitives can implement dense networks and support convolution lowered into matrix operations. They also form building blocks for attention and recurrent/spiking updates. Complete model support depends on the software mapping and remaining operators; an INT8 MAC alone is not a complete model runtime.

Start area/bandwidth experiments with one MAC lane and compare two lanes. The old four-lane LIF proposal is not a prediction of the right multiplier count for this design. INT4 weights are an extension to evaluate after INT8 numerical correctness and memory throughput are established.

Quantization must be part of the contract. Per-channel and per-group scales are not interchangeable: plain accumulation of integer partial sums followed by a single scale is insufficient when groups use different scales. The [llama2.c quantized runtime](https://github.com/karpathy/llama2.c/blob/master/runq.c) uses group scales and still retains floating-point state and other calculations. Its existing model format is not automatically compatible with a new fixed-point engine.

## Review of the pasted weight-streaming proposal

The main idea is sound: off-chip storage decouples logical model size from physical arithmetic-unit count. Keeping arithmetic fed matters more than adding idle lanes.

The following estimates need refinement:

1. **On-chip storage:** 64–128 bytes is a candidate allocation, not an established capacity limit. Talos 1's flip-flop area is a useful starting estimate, but read muxes, writes, buffering, multipliers, physical cells, and routing determine actual fit. No SRAM/latch-based savings are assumed.
2. **Memory throughput:** quad SDR payload capacity is `4 * QSPI clock / 8` bytes/s. Thus 20 MHz gives an ideal 10 MB/s. Commands, addresses, dummy cycles, turnarounds, RAM writes, and activation reads reduce useful throughput. One byte per INT8 weight is only the weight portion of the traffic.
3. **Language-model dimensions:** the [documented stories260K configuration](https://github.com/karpathy/llama2.c/blob/master/doc/stories260K.md) uses dimension 64, five layers, eight query heads, four KV heads, and context 512. Applying the [model's feed-forward sizing rule](https://github.com/karpathy/llama2.c/blob/master/model.py) gives hidden dimension 172. Therefore a 64-element input buffer requires tiling even for this model.
4. **Attention and cache:** for that configuration, calculated fixed-weight dense work is 259,328 MACs/token. At context length L, attention adds approximately `2 * 5 * 64 * L = 640L` MACs/token. At L=512 this is 327,680 additional MACs, before softmax and other operations. It cannot be omitted from a full-token timing estimate.
5. **Cache capacity:** the KV width is 32. At L=512, K and V together contain `2 * 5 * 512 * 32 = 163,840` values: 160 KiB at one byte/value or 640 KiB with the reference runtime's floats. An INT8 cache would require its own accuracy validation and scale metadata. External writable storage and access policy matter from the start if long-context operation on small hosts is an objective.
6. **Tokens/s:** roughly 25.9 ms for dense INT8 weight payload at an assumed useful 10 MB/s is an idealized component estimate. It excludes attention, extra memory traffic, quantization/scales, host transfers, nonlinear operations, and scheduling. The proposed 10–30 tokens/s range is unverified.
7. **Host duties:** normalization, activation functions, softmax, and attention have costs that vary by host and context. Moving cache storage to PSRAM alone does not solve host-side arithmetic or memory-access bottlenecks.

## Next concrete experiments

1. Specify exact integer operations, scale formats, overflow rules, and external-memory transactions.
2. Build a cycle/byte accounting model for a small MLP, a small convolutional task, and stories260K-style inference. Include chunking, attention, and host duties.
3. Validate quantized model outputs against a reference, including the 172-element hidden layer and non-multiple tile tails.
4. Synthesize a minimal MAC, input buffer, accumulator bank, sequencer, and memory interface early. Measure one- and two-lane candidates.
5. Choose frequencies and memory parts from measured routed timing and carrier/shuttle limits. Retain the earlier note's distinction between typical-corner success and wider timing closure.

Spiking support remains an optional application of the arithmetic and state machinery. Its priority has not been reaffirmed by the user and should not constrain the general NPU design without further workload evidence.
