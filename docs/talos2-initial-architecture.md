# Talos 2: initial architecture evidence and candidate

Status: design exploration, 13 October 2026. No Talos 2 RTL or frequency target has been signed off.

Direction update: the user has clarified that a custom carrier board is allowed, with a PCB grant from the HackClub event, and that Talos 2 should be a broadly programmable NPU with potential tiny language-model support. The four-lane reservoir below is now a historical candidate, not the preferred starting architecture. See [the programmable NPU direction](talos2-programmable-npu-direction.md). The Talos 1 measurements remain relevant baseline evidence.

## Constraints and intent

- Target approximately 64 neurons and better practical performance with microcontroller hosts.
- Four tiles (2x2) are the current budget. Additional area requires a later decision.
- The organizer's supplied message describes approximately 340 x 160 micrometres per tile and offers four tiles for 64 neurons. Exact usable core dimensions must come from the selected flow.
- The user is interested in broader NPU functionality, with architecture still open. A spiking reservoir and a programmable integer neural-network accelerator are different designs; simply increasing the reservoir size does not add conventional neural-network support.

## Talos 1 physical-design evidence

Source: [successful GDS run 38406827808](https://github.com/kazenoko-git/Talos/actions/runs/38406827808), commit `11870abcbd98e69436ee9bf455c244d88d20ecdf`. These reports describe that committed design, not the locally modified working tree.

Downloaded `GDS_logs` to `/tmp/talos1-gds-38406827808`; paths below are relative to its `runs/wokwi` directory.

| Metric | Reported value | Source |
| --- | --- | --- |
| Clock period | 62.5 ns (16 MHz) | Post-route setup report |
| Die dimensions | 346.64 x 160.72 micrometres | Global placement log |
| Core area | 51,966.970 square micrometres | Global placement log |
| Synthesized cell area | 38,745.280 square micrometres | Global placement log, before pin-density area adjustment |
| Placer utilization | 85.997% | Global placement log, after pin-density area adjustment |
| Final standard-cell utilization | 81.0079% | `final/metrics.json` |
| Final standard-cell area | 42,097.4 square micrometres | `final/metrics.json` |
| Sequential-cell area | 18,387 square micrometres | `final/metrics.json` |
| Worst setup slack, max-wire typical corner | +22.5466 ns | `final/metrics.json`, `max_tt_025C_3v30` |
| Worst setup slack, max-wire slow corner | -13.7428 ns | `final/metrics.json`, `max_ss_125C_3v00` |
| Setup violation count, max-wire slow corner | 309 | `final/metrics.json`; do not interpret the aggregate across corners as unique failing paths |
| Timing-checker gating corners | `*tt*` | `67-checker-setupviolations/config.json` |

The green workflow therefore does not establish timing closure at every analyzed process/voltage/temperature corner. It also does not prove that every reported slow-corner violation is functionally sensitizable.

The worst reported path is `_2519_` (`u_regs.state`) to `_2428_` (`u_reservoir.v_mem[9][0]`). See `54-openroad-stapostpnr/max_ss_125C_3v00/max.rpt` and `final/nl/tt_um_kazenoko_talos.nl.v`.

The RTL shares the membrane read port between inspection and computation. Inspection addressing depends on register-controller state; the neuron ALU consumes that shared port. While `busy` is high, the computation address is selected; while idle, membrane writes are disabled. This suggests a functionally blocked path, but formal/path-sensitization analysis and the other reported violations remain necessary before declaring a timing exception. Do not blanket-disable these paths or derive a certified maximum frequency from this slack.

## Performance accounting

Clock rate, neuron-update throughput, complete-network step rate, and host-visible sample throughput must be reported separately.

Talos 1 accepts a step on one edge and performs 16 neuron updates on the next 16 edges. At 16 MHz, computation after acceptance takes 1 microsecond; back-to-back accepted steps require at least 17 clock periods with the current controller.

An ordinary input write, step write, and two separate spike-register reads transfers 8 SPI bytes (64 bits). At 1 MHz SPI that is at least 64 microseconds, before chip-select gaps and software overhead. Using the existing burst read for the two spike bytes reduces this to 7 bytes. This already exceeds compute latency substantially.

For a 64-neuron design, the spike bitmap alone is 8 bytes and a full 8-bit membrane snapshot is 64 bytes. At 1 MHz SPI those payloads take 64 and 512 microseconds respectively. Debugging every membrane every step should not be the required application interface.

## Candidate to evaluate

Start with four neuron-processing lanes, each with a 16-neuron state bank, sharing one host interface. The lanes are logical units, not isolated physical tiles; cross-bank recurrence must preserve the intended network.

Ideal update work, excluding trigger, pipeline fill/drain, and result publication:

| Configuration | Clock | Update cycles for full network | Compute time |
| --- | --- | --- | --- |
| Talos 1: 16 neurons, one lane | 16 MHz | 16 | 1 us |
| 64 neurons, one lane | 16 MHz | 64 | 4 us |
| 64 neurons, four lanes | 16 MHz | 16 | 1 us |
| 64 neurons, four lanes, exploratory target | 32 MHz | 16 | 0.5 us |

The 32 MHz row is arithmetic for a proposed experiment, not a demonstrated achievable clock. Area and routing also remain unmeasured for these candidates.

Split the address/read/current work and neuron integration/threshold/write work into shorter pipeline stages as timing evidence directs. Independent neuron states allow successive neurons to occupy different pipeline stages. Preserve previous-step spikes until every lane finishes, latch inputs/settings at acceptance, and publish the completed output atomically.

Evaluate a two-lane implementation as an area/performance alternative if four lanes consume too much of the budget. Compare complete-step latency, throughput, and host bandwidth rather than selecting the highest clock number alone.

## Communication direction

Retain ordinary SPI as the common host interface. Add:

- Burst input and result transfers, including an input-and-step command.
- A small pending-input buffer and completed-result buffer, with explicit acceptance and overflow behavior.
- A result-ready pin/status flag and sequence number.
- Stable result reads while the next step computes.
- Optional processing of a sequence before readout, with on-chip feature accumulation evaluated against its storage cost.

First define the required sample rate and payload. Faster SPI can then be implemented either with sufficiently fast system-clock sampling and proven timing bounds, or an SCLK-clocked serial block with a proper clock-domain crossing to the core. The latter requires additional clock constraints and verification; it is not a drop-in RTL substitution. No SPI speed beyond the measured baseline is promised yet.

## Scope of NPU programmability

Physical arithmetic-unit count is not model size: time multiplexing can execute more logical operations than there are physical units. LLM feasibility depends heavily on supported operations, weight/activation memory, bandwidth, and latency.

For scale, 64 eight-bit membrane states need 64 bytes; a dense 64-by-64 eight-bit weight matrix needs 4,096 bytes before activations and control. Talos 1's inferred memory is mapped to flip-flops, so cheap SRAM must not be assumed. Programmable sparse connectivity, parameter banks, and a small readout engine are candidates whose area and usefulness need measurement before inclusion.

## Next engineering work

1. Resolve baseline timing constraints and distinguish functional paths from blocked inspection paths.
2. Build a parameterized reference model and compare one-, two-, and four-lane candidates with pipelining.
3. Measure synthesis area and routed timing at candidate clock periods; verify the GF180 carrier's clock and I/O limits separately.
4. Specify and test the burst protocol, backpressure, reset, and clock-domain behavior.
5. Evaluate a real temporal task against a host-only baseline before claiming practical ML acceleration.
