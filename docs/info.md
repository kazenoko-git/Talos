# Talos: 32-Lane Neuromorphic Micro-NPU for GF180MCU

Talos is a custom digital ASIC designed for the GlobalFoundries GF180MCU process node via the Hack Club "Basics of ASICs" YSWS through wafer.space Run 3 MPW. It functions as a hardware neuromorphic co-processor, acting as a neural engine of sorts for microcontrollers to run Edge AI models (e.g. Arduino Uno, ESP32, Raspberry Pi Pico / RP2040).

---

## How it works

### 1. Multiplier-Free Compute Architecture
Standard digital multipliers require hundreds of standard cells per unit, making dense parallel arrays impossible on a 1x1 Tiny Tapeout tile (~160µm × 100µm). Talos solves this by implementing multiplier-free discrete arithmetic:

* **Mode 0: BitNet b1.58 Ternary Mode (Default):**
  * Weights are ternary: $W \in \{-1, 0, +1\}$, encoded with 2 bits (`2'b00` = 0, `2'b01` = +1, `2'b11` = -1).
  * Activations are 8-bit signed two's complement integers ($A \in [-128, +127]$).
  * 32 parallel 3-way multiplexers select $+A$, $-A$ (two's complement negation), or $0$ sign-extended to 9 bits signed.
* **Mode 1: 1-Bit Binary Neural Network (BNN Mode):**
  * Weights and activations are binary bits ($1 \to +1, 0 \to -1$).
  * 32 parallel XNOR coincidence detection gates + popcount adder tree.

### 2. 5-Level Balanced Adder Tree
All 32 lane products are summed in a single clock cycle through a balanced 5-level binary adder tree ($32 \to 16 \to 8 \to 4 \to 2 \to 1$), producing a 14-bit signed chunk sum.

### 3. 24-Bit Saturation Accumulator
The 14-bit chunk sum is added into a 24-bit running accumulator. This is useful for vector chunking, as microcontrollers can stream vectors of arbitrary length (e.g., 256, 512, 1024 elements) across consecutive 32-element bursts. Hardware saturation clamps arithmetic at $+8,388,607$ (`0x7FFFFF`) or $-8,388,608$ (`0x800000`) to prevent overflow wrap-around errors.

### 4. Fused Activation Unit
The hardware integrates post-processing directly on-chip:
* **ReLU:** Clamps negative accumulator values to 0.
* **8-Bit Clamping:** Clamps the 24-bit accumulator into $[-128, +127]$, accessible in a single SPI read at register `0x05`.

---

## Register Map & SPI Interface

Talos communicates over standard SPI Mode 0 ($CPOL=0, CPHA=0$) with internal 3-stage synchronizers to completely remove any possibility of metastability on the 16 MHz clock.

| Address | Name | Access | Description |
| :---: | :---: | :---: | :--- |
| **`0x00`** | `CTRL` | R/W | Bit 0: `rst_acc` (1=clear acc), Bits 2:1: `mode` (00=BitNet, 01=BNN), Bit 3: `act_en` (1=ReLU). |
| **`0x01`** | `STATUS` | R | Bit 0: `busy`, Bit 1: `overflow`, Bit 2: `irq`. |
| **`0x02`** | `ACC_LOW` | R | Accumulator bits `[7:0]` (auto-increments on burst read). |
| **`0x03`** | `ACC_MID` | R | Accumulator bits `[15:8]`. |
| **`0x04`** | `ACC_HIGH` | R | Accumulator bits `[23:16]`. |
| **`0x05`** | `ACT_OUT` | R | 8-bit clamped/ReLU activation result. |
| **`0x10`** | `STREAM` | W | Burst stream port. Writing 64 bytes (32 activations + 32 weights) triggers auto-compute. |

---

## Pinout Mapping

| Pin | Name | Direction | Function |
| :--- | :--- | :---: | :--- |
| `ui_in[0]` | `sclk` | Input | External SPI Clock (up to 16 MHz). |
| `ui_in[1]` | `mosi` | Input | Master-Out Slave-In serial data. |
| `ui_in[2]` | `cs_n` | Input | Active-low SPI Chip Select. |
| `ui_in[7:3]` | `unused` | Input | Tied high/low internally. |
| `uo_out[0]` | `miso` | Output | Master-In Slave-Out serial data. |
| `uo_out[1]` | `busy` | Output | High while calculation is executing. |
| `uo_out[2]` | `irq` | Output | Completion interrupt pulse. |
| `uo_out[7:3]` | `acc_dbg[4:0]` | Output | Top 5 bits of accumulator for oscilloscope monitoring. |
| `uio[7:0]` | `unused` | High-Z | Safe bidirectional pins set to high-impedance inputs. |

---

## How to test

### Simulation (cocotb + iverilog)
1. Ensure `iverilog` and Python `cocotb` are installed.
2. In the `test/` directory, run:
   ```bash
   make clean && make
   ```
3. Inspect generated waveform traces with Surfer:
   ```bash
   surfer test/tb.fst
   ```

### Microcontroller Firmware Example (Arduino / C++)
```cpp
#include <SPI.h>

const int CS_PIN = 10;

void setup() {
  SPI.begin();
  pinMode(CS_PIN, OUTPUT);
  digitalWrite(CS_PIN, HIGH);

  // Reset Accumulator & Enable ReLU
  digitalWrite(CS_PIN, LOW);
  SPI.transfer(0x00); // Write CTRL
  SPI.transfer(0x09); // rst_acc=1, act_en=1
  digitalWrite(CS_PIN, HIGH);

  // Stream 32 Activations + 32 Weights
  digitalWrite(CS_PIN, LOW);
  SPI.transfer(0x10); // Stream Port
  for (int i = 0; i < 32; i++) SPI.transfer(10); // Activations = 10
  for (int i = 0; i < 32; i++) {
    // 16 of (+1) -> 0x01, 8 of (0) -> 0x00, 8 of (-1) -> 0x03
    if (i < 16) SPI.transfer(0x01);
    else if (i < 24) SPI.transfer(0x00);
    else SPI.transfer(0x03);
  }
  digitalWrite(CS_PIN, HIGH);

  // Read 24-bit Result: Expected = 80 (0x50)
  digitalWrite(CS_PIN, LOW);
  SPI.transfer(0x82); // Read ACC_LOW with auto-increment
  uint8_t low  = SPI.transfer(0x00);
  uint8_t mid  = SPI.transfer(0x00);
  uint8_t high = SPI.transfer(0x00);
  digitalWrite(CS_PIN, HIGH);

  int32_t result = (high << 16) | (mid << 8) | low;
  Serial.print("Output: ");
  Serial.println(result);
}

void loop() {}
```

---

## External hardware

* **Carrier / Breakout Board:** Carrier PCB designed to plug directly into Arduino Uno, Raspberry Pi Pico or ESP32 as an expansion shield.
* **Host Microcontroller:** Any 3.3V logic MCU (e.g. Raspberry Pi Pico, ESP32, Arduino Uno with level shifter) connected to `sclk`, `mosi`, `miso`, and `cs_n`.
* **Testing Hardware:** IcePi Zero FPGA board provided by Hack Club.
