# Talos 2: preliminary ternary-A8 area budget

13 October 2026. This is a storage/structural calculation, not synthesis or physical-design evidence for Talos 2.

## Available rectangle and estimated core

The current [GF180 tile-size table](https://github.com/TinyTapeout/tt-support-tools/blob/main/tech/gf180mcuD/tile_sizes.yaml) defines 2x2 as 711.20 x 325.36 micrometres, or 0.231396 mm2. The ttgf26c GDS action's default support-tools ref is main.

Talos 1's actual floorplan has 3.36 micrometre left/right margins and 3.92 micrometre top/bottom margins. Applying the same margins gives a preliminary 2x2 core estimate of:

`(711.20 - 6.72) * (325.36 - 7.84) = 223,686.49 um2 = 0.223686 mm2`.

This extrapolation must be checked against an actual 2x2 floorplan. It is not the area available to fill with logic: placement space, physical cells, clock distribution, and timing repair still matter. A 65-70% standard-cell utilization target is a proposed planning target, not a shuttle rule or a routing guarantee. It corresponds to about 0.1454-0.1566 mm2 of standard-cell area.

## Storage budget

The [GF180 resettable DFF cell](https://gf180mcu-pdk.readthedocs.io/en/latest/digital/standard_cells/gf180mcu_fd_sc_mcu7t5v0/cells/dffrnq/gf180mcu_fd_sc_mcu7t5v0__dffrnq_1.html) has area 74.6368 um2. This matches the type used for 240 of Talos 1's 246 sequential cells. Its measured average sequential-cell area, including six settable DFFs, is 74.7439 um2 per cell.

The following calculations use resettable DFFs throughout. They do not assume SRAM macros or latch-based savings.

| Storage | Bits | DFF area (mm2) | Status |
| --- | --- | --- | --- |
| 64-byte activation buffer | 512 | 0.038214 | Candidate size |
| Four INT32 partial sums | 128 | 0.009554 | Candidate count |
| Control, addresses, serial/pipeline state | 256-384 | 0.019107-0.028661 | Planning allowance, not an implemented register count |
| Total above | 896-1,024 | 0.066875-0.076428 | Storage-only subtotal |

This subtotal excludes input selection, write enables, decode, arithmetic, output scaling, SPI, QSPI control, sequencing logic, synchronization, and clock/physical overhead. The control-bit allowance must be replaced by a register inventory once the operation protocol is specified.

## Buffer-access cost is material

A straightforward binary mux tree for one 64-byte read port requires `8 * (64 - 1) = 504` two-input mux functions. Holding individually enabled storage bits can require another 512 mux functions. Mapping all 1,016 functions to the [MUX2_X2 cell](https://gf180mcu-pdk.readthedocs.io/en/latest/digital/standard_cells/gf180mcu_fd_sc_mcu7t5v0/cells/mux2/gf180mcu_fd_sc_mcu7t5v0__mux2_2.html), area 32.928 um2, gives about 0.033455 mm2 before address decoding.

This is an illustrative structural implementation, not an upper bound or a predicted synthesis result. Mapping may use different cell strengths, larger muxes, shared decode logic, or a different sequential-access buffer organization. Accumulator selection/holding and other registers also have additional access logic.

Storage plus this activation-access example totals approximately 0.1003-0.1099 mm2. Against the proposed 65-70% cell-area target, that leaves approximately 0.0355-0.0563 mm2 for everything else. Whether that remainder is sufficient for the complete controller/datapath must be measured.

## External weights are essential to this proposal

A dense 64x64 ternary matrix has 4,096 weights. At two bits per weight it needs 8,192 bits, or 1 KiB, excluding scales/metadata.

DFF storage alone would occupy `8192 * 74.6368 = 611,424.67 um2 = 0.611425 mm2`: more than the entire 2x2 rectangle. The intended design therefore stores weights externally and retains only a small packed-word/stream buffer on chip. Its larger activations and recurrent state also live in external RAM. A sparse on-chip network would have a different capacity calculation.

## Feasibility judgment and measurement boundary

A compact streamed-weight ternary-A8 implementation is plausible within 2x2. This calculation establishes manageable basic storage and a clear reason to avoid on-chip dense weight storage; it does not establish total fit or operating frequency.

Start with one add/subtract/accumulate datapath, one 64-byte input buffer, a small accumulator bank, serial memory control, and deliberately simple fixed-point scaling. Floating-point group scaling, large queues, activation double-buffering, multiple read ports, and parallel lanes must not be added without new measurements.

If synthesis is too large, a 32-byte buffer saves 256 DFFs (about 0.0191 mm2) plus some access logic. Reducing four INT32 sums to one saves another 96 DFFs (about 0.0072 mm2) plus selection logic, at a potential memory-traffic/performance cost. These choices preserve the ability to process larger logical vectors through tiling.

The next proof should include synthesis of the entire minimal engine (SPI, memory control, datapath, storage, scaling, and sequencer), followed by 2x2 placement/routing and appropriate timing checks. Synthesizing the adder alone would not answer the fit question.
