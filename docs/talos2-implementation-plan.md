# Talos 2 implementation plan

Prepared for work starting **14 October 2026**. This is a staged engineering plan, not a claim that the proposed circuit already fits or meets timing.

## 1. What we are building

Talos 2 is a small programmable accelerator for embedded inference: **ternary weights, signed INT8 activations, and wider integer accumulation**. Its first job is to execute trained dense layers and short layer sequences using external model and working memory.

The current area limit is **2×2 tiles**. “64 neurons” becomes a useful initial workload size, not a limit of 64 permanently wired neurons. A shared engine can process larger layers over multiple passes, subject to memory and latency limits.

This plan supersedes the alternative architectures in [the initial architecture note](talos2-initial-architecture.md) and [the programmable direction discussion](talos2-programmable-npu-direction.md). Those remain useful background. [The area budget](talos2-area-budget.md) supplies preliminary estimates, not a final fit result.

### Required for the first complete version

- Programmable weights in {−1, 0, +1}; signed INT8 inputs and outputs.
- One shared add/subtract/accumulate engine, with INT32 partial sums.
- Matrix-vector multiplication, bias, output requantization, saturation, and optional ReLU.
- Host SPI commands, readable status/errors, and a completion indication.
- ASIC-controlled external memory access, so the host does not feed every weight.
- At least a two-layer sequence that retains intermediate results in external RAM.
- A bit-exact software reference, automated RTL tests, physical FPGA validation, and routed area/timing evidence.

### Initial candidates, to be measured

| Item | Starting candidate | Decision rule |
|---|---|---|
| Input buffer | 64 bytes | Reduce to 32 if access logic/storage prevents fit |
| Partial sums | Four INT32 registers | Reduce to one if the complete design cannot fit |
| Compute | One ternary arithmetic engine | Add lanes only after measuring memory supply and useful speedup |
| Model storage | External flash | Verify actual memory protocol and programming route |
| Working memory | One external RAM device | Select a compatible part and validate burst behavior |
| Memory interface | Shared QSPI bus, separate chip selects | Begin in ordinary SPI mode; earn QSPI through testing |
| Output scaling | Per-output integer multiplier and shift | Measure accuracy and hardware cost before freezing |
| Clock | Conservative bring-up clock, then sweep | Set advertised limit from constraints, route, and hardware evidence |

Convolution acceleration, elementwise operations, native spiking updates, extra lanes, and language-model experiments are later features. Dense lowering can express some workloads, but its memory and transfer costs must be counted. Version 1 does not promise attention, general nonlinear functions, floating-point execution, or compatibility with an existing ternary LM format.

## 2. Why this should exist

The useful hypothesis is that a small MCU can launch inference and continue other work while Talos handles model reads, arithmetic, and intermediate storage. This could also keep a model out of scarce MCU RAM. Faster inference and lower energy are **questions to test**.

Compare against a competent host-only implementation of the **same quantized model**, including preprocessing, transfers, and postprocessing. Use the actual original ESP32, ESP8266, Uno/Mega, and Pi 3B as separate targets where available; do not transfer measurements between variants. Start with one available ESP32 and add the other hosts after the protocol works.

Record end-to-end latency, host CPU occupation, model/working RAM, accuracy, and—where measurable—energy including external memory. A fast kernel with slow transfers is not a successful accelerator.

## 3. Numerical contract: freeze before writing the engine

The following is the proposed version-1 contract. Resolve changes here first, then update the reference, exporter, tests, and RTL together.

### Inputs, weights, and accumulation

- Activations are signed two's-complement INT8: −128 through +127; zero represents zero.
- Packed weight codes are `00 = 0`, `01 = +1`, `10 = −1`, `11 = invalid`.
- Decode and sign-extend before arithmetic. In particular, `−(−128)` must produce **+128**, not overflow an INT8 temporary.
- Compute each output as `acc = bias + sum(weight[k] * input[k])`, with signed INT32 bias and accumulation.
- Apply bias **once per output**, before its first input chunk.
- Proposed supported dimensions are `1 ≤ K, M ≤ 4096`; confirm counter and address cost before freezing these limits. The input buffer size is not the maximum K.
- The exporter checks conservative bounds: `abs(bias) + 128*K ≤ INT32_MAX`. Hardware reports arithmetic overflow if malformed data violates the contract; it must not silently turn it into an apparently valid prediction.

### Output scaling

Keep raw INT32 output as a bring-up/debug mode. For normal layers, propose:

`output = sat_int8(round_ties_away_from_zero(acc * multiplier / 2^shift))`

`multiplier` is unsigned 16-bit; `shift` is 0–31. Use sufficient signed product width (48 bits) and account for the rounding step. Shift zero has no fractional rounding; multiplier zero produces zero. Apply ReLU to the scaled result before final INT8 storage. Define every edge case in software tests, including negative half-way values.

This scaler still costs registers and arithmetic. Start with raw results and a shift-only scaler during bring-up; add the general multiplier/shift scaler using a serial implementation or shared arithmetic if that meets area and latency targets. **Shift-only scaling is an alternative numerical profile**, requiring model accuracy validation—not an invisible implementation shortcut.

The exporter converts trained per-output weight scales and activation scales into this integer representation. Bias is expressed in accumulator units. Per-group floating scales and transforms from other model formats are outside this contract. Train/fine-tune with ternary weights and activation rounding/clipping; measure the accuracy loss before committing to hardware precision.

## 4. Execution and memory layout

```text
Host SPI → command/status registers → job sequencer
                                      ↓
External flash/RAM ↔ memory controller ↔ input buffer
                                      ↓
                            ternary decode + shared adder
                                      ↓
                               partial sums → scaler
                                      ↓
                             output in external RAM → IRQ
```

### Tiled weights

For the starting four-output, 64-input configuration, one packed weight tile contains `4 × 64 × 2 bits = 64 bytes`.

Store tiles in output-block order, then input-block order. Within a tile, store one row at a time; pack four consecutive weight codes per byte, lowest two bits first. Pad incomplete rows/columns with zero codes. For row block `rb` and column block `kb`, the byte offset is:

`(rb * ceil(K / 64) + kb) * 64`

Load an input chunk, stream weights for four outputs through the one arithmetic engine, and retain those four partial sums across chunks. Once all K inputs are consumed, scale and store the valid outputs. Then advance to the next row block. Padded positions do not contribute; padded outputs are never written.

This reuses each input chunk across four outputs. For K greater than the buffer, input chunks may need rereading for each output block. Include that traffic in the performance model. Keeping a whole small input vector cached is an optimization to test later.

The exported format must identify tile dimensions. Reducing buffer or accumulator count changes packing or traversal; update the format/version and capability reporting explicitly.

### Proposed descriptor ABI

Start with one matrix-vector opcode, not a processor instruction set. A proposed 32-byte, little-endian descriptor is:

| Offset | Field | Bytes |
|---|---|---:|
| 0 | Opcode | 1 |
| 1 | Flags: ReLU, raw INT32 output, last descriptor | 1 |
| 2 | Output count M | 2 |
| 4 | Input count K | 2 |
| 6 | Reserved, must be zero | 2 |
| 8 | Input address | 4 |
| 12 | Packed weight address | 4 |
| 16 | Output address | 4 |
| 20 | Per-output parameter address | 4 |
| 24 | Next descriptor address | 4 |
| 28 | Reserved, must be zero | 4 |

Each output's parameter record is eight bytes: INT32 bias, UINT16 multiplier, UINT8 shift, and one reserved zero byte. INT8 output stride is one byte; raw output stride is four bytes.

Use a documented logical memory map that distinguishes flash and RAM; one candidate uses address high byte `0x00` for flash and `0x01` for RAM with 24-bit device offsets. Reject unsupported regions and out-of-capacity ranges. Confirm capacities and addressing after choosing parts.

Descriptors and writable activations live in RAM. Weights/parameters may live in flash or RAM if the implementation supports both. Use two alternating output arenas for layer chains. **In-place matrix-vector execution is unsupported initially**, because it can overwrite an input before its last use.

Validate dimensions, flags, shifts, alignment, ranges, output overlaps, and address arithmetic. Bound descriptor traversal—for example, a configurable maximum of 256 layers—to stop a corrupt cyclic chain. The exact ABI is frozen only after the reference and complete area estimate agree.

## 5. Interfaces and RTL responsibilities

Keep modules small enough to test independently:

| Block | Responsibility |
|---|---|
| Top wrapper | Shuttle pin mapping, reset, output enables, safe idle states |
| Host SPI receiver/transmitter | Correct serial edge behavior and command framing |
| Command/status block | Capability/version registers, start, status, errors, abort |
| Memory controller | Device initialization, SPI/QSPI transactions, turnaround, limits |
| Memory arbiter | Exclusive job/host transfer ownership |
| Input buffer | Byte storage and defined read/write behavior |
| Ternary decoder/adder | Signed add/subtract and invalid-code detection |
| Partial-sum bank | Persistent output state across chunks |
| Scaler | Exact rounding, saturation, optional ReLU |
| Job sequencer | Descriptor validation, tile traversal, completion and failures |

Use one core clock initially. Generate memory-clock transitions with clock enables rather than introducing a gated internal clock. Specify memory output/input delays and sampling phase from the chosen device and board assumptions. External-memory timing does not disappear because the controller uses one clock.

Talos 1's host SPI test samples MISO late in a clock phase; that alone does not validate a real master's sampling edge. New tests must sample at the selected SPI-mode edge, vary phase against the core clock, and check CS truncation. An oversampled SPI implementation needs documented minimum high/low times. Use a separate SPI clock domain only if required, with an explicit CDC design and constraints.

Latch job settings at launch. Status/debug reads must not redirect active arithmetic or change a running job's parameters. Keep immutable job configuration separate from host-visible registers.

### Host transfers and concurrency

Provide commands for register reads, configuration, bounded memory reads/writes, start, and abort. Assign opcodes and exact frame bytes in the protocol spec before driver work.

For initial memory transfers, reuse the input buffer while the engine is idle:

1. A host read request supplies address and length, up to the advertised buffer capacity.
2. The controller fetches the complete block and sets `TRANSFER_READY`.
3. A separate host transaction retrieves the buffered bytes at a defined SPI rate.
4. Writes collect a complete bounded payload before launching the memory transaction.

This avoids assuming the host can pause a streaming SPI packet whenever memory stalls, and avoids a second large transfer buffer. Starting a job requires pending transfers to finish or be explicitly cleared. While a job runs, allow status and abort; reject conflicting memory commands without corrupting the job. Keep command errors distinct from job errors.

Document CS-abort semantics, timeouts, sticky errors, IRQ acknowledgment, and reset behavior. An abort can leave partial external writes; outputs become valid only after successful DONE. Reset/abort must return chip selects and bidirectional output enables to safe states.

### Candidate pin allocation

Subject to the actual shuttle wrapper and final connector pinout:

- Host: `ui[0]` SCK, `ui[1]` MOSI, `ui[2]` CS; `uo[0]` MISO, `uo[1]` IRQ, `uo[2]` BUSY.
- Memory: `uio[3:0]` IO0–IO3, `uio[4]` memory SCK, `uio[5]` flash CS, `uio[6]` RAM CS, `uio[7]` spare.
- Reserve remaining host inputs/outputs only after checking clock/reset/project-selection arrangements.

Treat this as a pin-budget proposal, not permission to lay out a PCB against an assumed connector revision.

## 6. Area and timing gates

The currently published GF180 2×2 rectangle is 711.20 × 325.36 µm, about **0.2314 mm² gross**. An estimate applying Talos 1 margins gives roughly 0.2237 mm² core; the actual generated floorplan must confirm this. See [official tile definitions](https://github.com/TinyTapeout/tt-support-tools/blob/main/tech/gf180mcuD/tile_sizes.yaml).

The existing preliminary budget assigns approximately 0.0669–0.0764 mm² to flip-flop storage and another illustrative 0.0335 mm² to activation-buffer access logic. These are structural estimates. Controller state, accumulator access, scaling, memory interface, and physical overhead still need accounting. Do not budget memory from bit count alone.

A dense 64×64 matrix with two-bit ternary codes is 1 KiB. Implementing it as resettable flip-flops would exceed this tile budget by itself. External storage is fundamental to this proposal; an available SRAM macro would require a separate confirmed integration plan.

Use roughly 65–70% standard-cell utilization as an early planning target, not a pass/fail law. Increase density only when routed results support it. Density is improved through synthesis/placement and measured design choices; unused area is not a reason to add RAM.

### Required measurement sequence

1. Establish the correct shuttle/template revision and reproducible synthesis/route toolchain. Local Yosys/OpenROAD are not currently confirmed installed.
2. Synthesize storage plus access logic, arithmetic, scaler, and interfaces separately to locate costs.
3. Synthesize the **complete minimal engine**, including controller and memory path.
4. Run early placement/routing in 2×2, inspect congestion and critical paths, then iterate.
5. Repeat complete route after feature changes; record revision, constraints, tool versions, area, utilization, and per-corner slack.

Talos 1's downloaded run reported about 81% final utilization, while a placement metric was near 86%. It passed the configured typical-corner timing gate but reported negative slow-corner setup slack. Therefore “green workflow” and “16 MHz target” are not sufficient proof of operating frequency. Confirm the required shuttle corners, constrain external interfaces, and report all relevant corners. Do not hide paths with broad false-path exceptions.

If the full design does not fit: remove optional operations/debug features; reduce buffer 64→32; reduce partial sums 4→1; reconsider scaler/profile with accuracy measurements. Preserve a useful complete inference path. If memory bandwidth is limiting, more arithmetic lanes may waste area. If communication dominates, extra input storage only helps if it eliminates measured transfers.

## 7. Verification and software deliverables

### Bit-exact reference and exporter

Build a pure software oracle directly from unpacked matrices, independently of RTL traversal. Separately implement packing and tiled execution, and require exact agreement. Export model files, parameter records, descriptors, a memory map, expected outputs, and a manifest recording format and numerical-profile versions.

Test all 256 activation values against every weight code, including the invalid code; −128 negation; bias once across chunks; rounding ties; saturation; overflow; zero scales; and ReLU. Cover M = 1, 3, 4, 5 and K = 1, 63, 64, 65, 127, 128, plus configured maximum limits and invalid dimensions. Use random matrices and hand-computable examples, not only repeated patterns.

### RTL and integration tests

- Arithmetic/buffer/scaler units: compare with the independent oracle.
- Host protocol: real sampling edges, clock-phase sweeps, minimum pulse widths, CS aborts, malformed frames, busy conflicts, reset mid-command.
- Memory model: initialization, single/quad modes, read latency, bus turnaround, tri-state behavior, burst boundaries, device-specific write restrictions.
- Engine: tails, multiple input chunks, multiple output blocks, parameter addressing, raw and quantized outputs.
- Sequencer: two-layer and longer chains, bad descriptors, cycles, overlap errors, completion/IRQ, reset and abort at different stages.
- Gate-level smoke tests: reset, protocol, signed arithmetic edge cases, tails, and a short layer chain with relevant timing annotation where supported.

Configure CI to select the new test modules explicitly. The existing default selects only `test`; it does not automatically execute every benchmark. Keep generated build products outside tracked source. Pin a verified compatible toolchain once the new project works.

### Host software

Write a small C driver with transport callbacks, capabilities, memory transfer helpers, model upload, descriptor launch, completion polling/IRQ, and error recovery. Add an ESP32 example first, then Arduino/ESP8266 adapters and a Pi host utility. Polling must work even on hosts without convenient IRQ support.

Measure upload/initialization separately from steady-state inference, and report both. Establish a documented flash-programming path; runtime inference and model installation are different operations.

### Workloads and baselines

Use three small dense workloads: a sensor classifier, a numerical estimator/forecaster, and a small autoencoder or reconstruction task. For each, compare floating-point software, ternary/INT8 software, and accelerator results. Hardware outputs must match the quantized oracle; quantized accuracy must meet a target chosen before final evaluation.

Split by sessions/subjects/time where appropriate. Prevent identical sequences, overlapping windows, or direct label leakage across training and evaluation. Include a simple non-neural baseline and a competent host-only neural implementation. Talos 1's ten demos are useful smoke tests, but their synthetic perfect scores do not establish general task accuracy or accelerator advantage.

## 8. Carrier board and physical bring-up

The supplied chip-on-board module connects to a carrier through a mating mezzanine connector. The connector is soldered to the carrier; the module plugs into it. Use the organizer-confirmed module revision, footprint, pinout, orientation, and clearance—not a guessed bare-chip footprint.

Reference: [wafer.space packaging update](https://www.crowdsupply.com/wafer-space/gf180mcu-run-2/updates/chip-on-board-packaging-progress) and [official PCB designs](https://github.com/wafer-space/chip-on-board-wire-bonded-pcbs). Run-2 examples do not guarantee Run-3 compatibility. The provided organizer messages authorize a custom carrier grant and reasonable PCBA costs.

Before layout, obtain the final connector specification, supply rails, IO voltage, reset/clock requirements, shared-chip project-selection signals, and supported assembly arrangement. Keep Uno/Mega's 5 V signals behind suitable level translation where required; GF180 naming alone does not establish safe voltage.

Select flash/RAM from current vendor datasheets. Check voltage, shared-bus mode compatibility, reset initialization, dummy cycles, maximum continuous transactions, wrap behavior, chip-select timing, and availability. Include power regulation/decoupling, programming access, host headers, safe CS pulls, test points, and clock/reset access. Route the memory bus short and validate its timing assumptions.

Physical FPGA bring-up order:

1. Read version/status and verify reset/IRQ behavior.
2. Write/read pseudorandom external RAM blocks across boundaries.
3. Read known flash contents and check bus direction changes.
4. Execute a tiny hand-calculated layer including input −128 and weight −1.
5. Run tail dimensions, then a two-layer chain.
6. Run an exported model and compare every output with the oracle.
7. Sweep clock/interface speed while checking correctness and inspecting signals with a logic analyzer or scope.

Use the FPGA prototype to validate the memory/host design before final carrier assembly. Later silicon bring-up repeats these steps at a conservative clock before any speed claim.

## 9. Work packages and exit criteria

| Stage | Deliverables | Exit criterion |
|---|---|---|
| A. Baseline and scope | Preserve Talos 1 revision/results; Talos 2 project and capability list | Reproducible baseline; no accidental mixing of old/new top-level designs |
| B. Numerical proof | Integer oracle, packing/export, three software model trials | Exact packed/unpacked agreement; acceptable measured quantized accuracy |
| C. Core bring-up | Buffer, arithmetic, partial sums, raw/scaled output tests | Exact oracle agreement on edges and tails |
| D. Interfaces and full area gate | Host commands, memory controller, complete minimal engine, early route | Fits 2×2 with credible timing; safe bus behavior; no unsupported memory assumptions |
| E. Autonomous inference | Descriptors, layer chain, C driver, exported model | Host launches a chain; intermediates stay in RAM; outputs exact |
| F. Physical and usefulness proof | FPGA demo, host comparisons, carrier design | Hardware verified; honest end-to-end results; connector/power design confirmed |
| G. Freeze and submission | Final RTL/docs/models, full checks, reproducible artifacts | Required timing/physical checks and event requirements satisfied |

Stages overlap sensibly: choose memory parts and ask for connector details during numerical work; start the protocol driver against a model before hardware is ready. Do not defer the complete area gate until all features are polished.

Suggested calendar, subject to actual progress and organizer cutoff:

| Dates, 2026 | Target |
|---|---|
| Oct 14–18 | Scope, numerical contract, oracle/export, initial model accuracy; memory/connector investigation |
| Oct 19–25 | Core and host protocol; module cost measurements; first complete design skeleton |
| Oct 26–Nov 1 | External memory and layer chain; complete 2×2 area/timing gate |
| Nov 2–8 | Physical FPGA validation, host driver, carrier prototype/design |
| Nov 9–15 | Model evaluation, host comparisons, performance and timing fixes |
| Nov 16–22 | Feature freeze, final route/checks, documentation and demonstration |
| Nov 23–30 | Repair buffer and submission against confirmed deadline |

The [event page](https://asic.hackclub.com/) currently states designs finish by the end of November, with fabrication in December. Confirm the exact submission cutoff. Physical silicon arrival is a later milestone; this schedule does not assume chips arrive before submission.

The [event resources](https://asic.hackclub.com/resources) require physical FPGA testing and say AI must not generate submitted ASIC designs. Use this plan as engineering guidance; author and understand the submitted RTL yourself, and confirm any unclear assistance boundary with the organizer.

## 10. Tomorrow: a concrete first session

1. **Preserve the baseline.** Record the current Talos 1 commit, local changes, and full test results. The last reviewed full run passed 16 tests. Create the Talos 2 working project from the correct shuttle template; keep Talos 1 available for comparisons. Do not copy unreviewed local edits over it.
2. **Write the one-page version-1 contract.** Fix signedness, packed codes, bias, rounding/saturation, supported dimensions, and required operations. Mark the four-sum/64-byte choices as candidates until area measurement.
3. **Implement the software oracle first.** Run a hand-computable 5-output × 65-input case, including −128, negative weights, chunk boundaries, and output tails. This is software work before RTL.
4. **Implement packing and compare it with the oracle.** A 5×65 matrix occupies four 64-byte tiles in the proposed format. Verify padding and row/block order explicitly.
5. **Record the open dependencies.** Obtain the final module/connector details and shortlist one compatible flash/RAM pair; identify the toolchain needed for complete synthesis/route.

Stop the first session with a saved contract, passing oracle/packing checks, and a short decision log. The next session can begin the smallest arithmetic RTL block with a clear expected result.

## 11. Definition of done

- The final precision, capabilities, tile layout, descriptor format, and host protocol are documented and versioned.
- A useful trained model survives quantization and matches the integer oracle on hardware.
- Multi-layer execution owns its memory traffic without host intervention between every layer.
- The complete design fits the actual 2×2 floorplan and meets the required constrained timing/physical checks.
- Automated tests and physical FPGA testing cover signed edge cases, tails, external memory, reset, errors, and completion.
- End-to-end host comparisons include transfer overhead and state the actual benefit or limitation.
- Carrier connector, rails, level translation, clock/reset, shared-chip selection, and assembly are confirmed.
- The submitted sources and reproduction instructions satisfy the organizer's requirements.

An area estimate, attractive GDS image, or synthetic 100% score alone does not close these gates. The goal is a small accelerator with a measured useful capability and a design you can explain.
