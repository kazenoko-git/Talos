# Talos: 16-Neuron Spiking Neuromorphic Reservoir

Talos is a 16-neuron recurrent Leaky Integrate-and-Fire (LIF) Liquid State Machine (LSM) digital ASIC. It is built with open-source GlobalFoundries 180nm (GF180MCU) standard cells on a single 1x1 tile for the Hack Club "Basics of ASICs" MPW run on wafer.space [7], [8].

It works as a neuromorphic temporal co-processor for microcontrollers like the ESP32, RP2040, Arduino, or Raspberry Pi. It takes complex, non-linear streaming time-series signals like audio keywords, biomedical ECG signals, IMU gestures and converts them into high-dimensional, linearly separable spike trains. LSMs are useful for this because they can capture time-dependent patterns without training a full recurrent neural network end-to-end [1].

> **In simpler terms:** Talos is a tiny custom chip that acts a bit like a small, brain-inspired pond. You drop signals into it, ripples move around between 16 simple "neurons," and it turns messy patterns over time into simple on/off pulses that a normal microcontroller can read. It is meant to help small computers notice patterns in sound, heartbeats, or motion.

## What is this thing, really?

A normal microcontroller is great at following instructions, but it is not always great at spotting patterns that unfold over time. Talos is a helper chip for that job - like an accelerator.

Think of it like this:

- **16 neurons** = 16 tiny buckets that slowly fill up with *"excitement."*
- **Leak** = the buckets slowly lose water over time, so they naturally forget old inputs.
- **Spike** = when a bucket gets full, it splashes out a short pulse.
- **Reservoir** = the buckets are connected in a small pond, so one splash causes ripples in others.
- **SPI** = a simple 4-wire language your microcontroller uses to talk to the chip.

You feed in signals over time. Talos mixes them into a rich pattern of pulses. Your microcontroller reads those pulses and can then use a simple classifier to tell, for example, "this sound looks like a keyword" or "this heartbeat looks unusual."

Note that this is NOT a general purpose CPU, and the goal is nowhere close to it. This is a specialized co-processor: small, low-power, and designed for temporal patterns.

## Why would you want one?

Because some signals are hard to understand as a single snapshot, and require more compute. They only make sense as a sequence over time.

Examples:

- Audio keyword spotting: "Hey device" versus background noise.
- Biomedical signals: ECG heartbeats that change shape over time.
- Motion gestures: IMU data from a wearable or robot.
- Sensor streams: vibration, pressure, or current signatures.

Talos turns those streams into spike patterns that are easier for a small computer to separate and classify.

## How it works

### 1. Biological Leaky Integrate-and-Fire (LIF) Neuron Cell (`lif_neuron.v`)

Each of the 16 neurons keeps an internal 8-bit signed membrane potential ($V \in [-128, +127]$). In plain terms: "how excited the neuron is right now."

It follows a discrete-time LIF update:

$$V[t] = V[t-1] - \text{leak}(V[t-1]) + I_{syn}[t]$$

The LIF model is a classic compromise. It is simple enough for digital hardware, but still captures the leaky integration, thresholding, and reset behavior that make spiking neurons useful for temporal processing [2], [3].

* **Configurable Arithmetic Leak:**
  * `2'b00`: No leak (lossless temporal integrator)
  * `2'b01`: Arithmetic shift `>>> 3` (12.5% decay per time step)
  * `2'b10`: Arithmetic shift `>>> 2` (25.0% decay per time step — default)
  * `2'b11`: Arithmetic shift `>>> 1` (50.0% decay per time step)
* **Threshold & Reset:** When $V \ge V_{th}$, the neuron fires a spike ($S[t] = 1$) and resets to baseline ($V[t] \gets 0$). In plain terms: when the bucket is full, it splashes and empties.
* **Readout Stability & Visual Retention:** Spikes are latched for the whole time-step. That makes SPI reads stable and keeps the carrier board LEDs visibly lit. In plain terms: the pulse is held long enough for your microcontroller and your eyes to see it.

### 2. Spiking Recurrent Reservoir Topology (`spiking_reservoir.v`)

The 16 neurons are wired into a multiplier-free recurrent reservoir with ternary synaptic weights ($W \in \{-1, 0, +1\} \times W_{scale}$). In plain terms: each connection is just "nudge positive," "nudge negative," or "do nothing," scaled by a number.

* **External Drive:** Neurons 0–7 get $+2 \times W_{scale}$ when external spike bits are injected over SPI.
* **Local Excitatory Recurrence ($+1$):** Neuron $(i-1) \pmod{16}$ adds $+W_{scale}$.
* **Local Inhibitory Recurrence ($-1$):** Neuron $(i+1) \pmod{16}$ adds $-W_{scale}$ (so it subtracts $W_{scale}$).
* **Long-Range Cross Recurrence:** Neuron $(i+5) \pmod{16}$ provides long-range feedback ($+W_{scale}$ for even neurons, $-W_{scale}$ for odd neurons).

This sparse recurrent topology gives you fading memory and high-dimensional phase-space trajectories without expensive on-chip multipliers or SRAM. The recurrent reservoir is what lets the LSM extract temporal features from input spike trains [1].

In plain terms, the neurons talk to each other in a small loop, recent inputs echo and mix, while old inputs fade. This creates a richer "fingerprint" of what just happened over time.

### 3. SPI Register Map (`reg_file.v`)

Standard SPI Mode 0 interface running up to 16 MHz. In Mode 0, the clock idles low and data is sampled on the rising edge (CPOL = 0, CPHA = 0) [4].

| Address | R/W | Name | Description |
| :--- | :--- | :--- | :--- |
| `0x00` | R/W | `CTRL` | Bit 0: Pulse `step_tick`, Bit 1: `soft_rst`; Read: Bit 2 = `busy` (1 while computing) |
| `0x01` | R/W | `V_TH` | 8-bit signed firing threshold (default: `+32`) |
| `0x02` | R/W | `W_SCALE` | 8-bit signed synaptic weight scale (default: `+12`) |
| `0x03` | R/W | `EXT_SPIKE`| 8-bit external spike injection vector for Neurons 0–7 |
| `0x04` | R | `SPIKES_LO` | Latched spike flags for Neurons 0–7 |
| `0x05` | R | `SPIKES_HI` | Latched spike flags for Neurons 8–15 |
| `0x06` | R/W | `LEAK_SEL` | 2-bit leak decay configuration (`00`=none, `01`=12.5%, `10`=25%, `11`=50%) |
| `0x10–0x1F`| R | `V_MEM[0..15]` | 8-bit signed membrane potentials (supports auto-increment burst reads) |

### 4. Pinout & Carrier Board Real-Time Visualization

| Pin | Direction | Signal | Function |
| :--- | :--- | :--- | :--- |
| `ui[0]` | Input | `sclk` | SPI Serial Clock |
| `ui[1]` | Input | `mosi` | SPI Master Out Slave In |
| `ui[2]` | Input | `cs_n` | SPI Chip Select (Active Low) |
| `ui[3]` | Input | `ext_tick`| Optional physical hardware step tick input |
| `uo[0]` | Output | `miso` | SPI Master In Slave Out |
| `uo[1..7]`| Output | `spike[0..6]` | Real-time spikes on **carrier board LEDs** |
| `uio[0..7]`| Output | `spike[7..14]`| Real-time spikes on bidirectional header |

## How to test

### 1. Automated Simulation (`cocotb`)

The full test suite runs locally with Icarus Verilog and cocotb. cocotb is a Python-based coroutine testbench environment that works with a bunch of simulators, including Icarus [5], [6].

```bash
cd test
make clean && make
```

The testbench checks:

1. SPI register reads, writes, and default configurations.
2. Leaky integration decay and subthreshold dynamics.
3. Threshold firing, spike latching, and potential reset.
4. Recurrent spatio-temporal reservoir reverberation across all 16 neurons.
5. Physical hardware pin stepping via `ui[3]`.

### 2. Testing on Physical Silicon (with Microcontroller)

1. Connect SPI lines (`sclk`, `mosi`, `miso`, `cs_n`) to an RP2040, ESP32, or Arduino.
2. Initialize parameters over SPI (write `0x01` for threshold, `0x02` for weight, `0x06` for leak).
3. In your main loop:
   * Write input spike events into register `0x03`.
   * Pulse bit 0 of register `0x00` (or pulse pin `ui[3]`) to advance the time step.
   * Read the 16-bit spike state from registers `0x04` and `0x05`.
   * Watch the carrier board LEDs (`uo[1..7]`) pulse with real-time neural activity!

## External hardware

* **Carrier / Breakout Board:** Hack Club carrier board with LEDs displaying spikes for Neurons 0–6 on `uo[1..7]`.
* **Host Microcontroller:** Any 3.3V logic MCU (e.g. Raspberry Pi Pico, ESP32, or Arduino Uno with level shifter) connected to SPI.
* **Testing Hardware:** IcePi Zero FPGA development board provided by Hack Club.

## References

[1] W. Maass, T. Natschläger, and H. Markram, "Real-time computing without stable states: A new framework for neural computation based on perturbations," *Neural Computation*, vol. 14, no. 11, pp. 2531–2560, 2002.

[2] W. Gerstner and W. M. Kistler, *Spiking Neuron Models: Single Neurons, Populations, Plasticity*. Cambridge, U.K.: Cambridge Univ. Press, 2002.

[3] G. Indiveri et al., "Neuromorphic silicon neuron circuits," *Frontiers in Neuroscience*, vol. 5, art. 73, 2011.

[4] Texas Instruments, "SPI Mode 0 transfer format," in *SPRU465: TMS320x2833x, 2823x Serial Peripheral Interface (SPI) Reference Guide*, 2009.

[5] cocotb developers, "cocotb documentation," [Online]. Available: https://docs.cocotb.org/

[6] HEPIC 2024, "What is cocotb?," Brookhaven National Laboratory, 2024.

[7] GlobalFoundries, "GF180MCU PDK," fossi-foundation/gf180mcu-pdk, GitHub. [Online]. Available: https://github.com/fossi-foundation/gf180mcu-pdk

[8] wafer.space, "Hack Club Basics of ASICs MPW run." [Online]. Available: https://wafer.space/

