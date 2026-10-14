# Talos 2 Numerical Contract (Version 1)

**Status:** Frozen specification for Talos 2 Version 1.  
**Audience:** Software reference oracle, model exporter, Verilog RTL, cocotb testbenches, and host drivers.

---

## 1. Data Types & Formats

### 1.1 Activations
- **Type:** Signed two's-complement 8-bit integer (`INT8`).
- **Range:** `[-128, +127]`.
- **Zero representation:** `8'h00 = 0`.
- **Extreme boundary:** `-128` (`8'h80`). Negation must yield `+128` (see Section 2).

### 1.2 Weights
- **Type:** 2-bit packed ternary code.
- **Encoding:**
  | Binary Code | Weight Value | Meaning |
  |---|---|---|
  | `2'b00` | `0` | Zero (no accumulation) |
  | `2'b01` | `+1` | Positive add |
  | `2'b10` | `-1` | Negative subtract |
  | `2'b11` | *Invalid* | Illegal code — triggers hardware error flag |

### 1.3 Accumulators & Bias
- **Type:** Signed two's-complement 32-bit integer (`INT32`).
- **Range:** `[-2,147,483,648, +2,147,483,647]`.
- **Bias:** Signed INT32 value applied **exactly once per output channel**, before processing its first input chunk.

---

## 2. Arithmetic & Accumulation

For each output channel $m \in [0, M-1]$:
$$\text{acc}_m = \text{bias}_m + \sum_{k=0}^{K-1} w_{m, k} \cdot x_k$$

### 2.1 Sign Extension & Negation
- When weight code is `2'b10` (`-1`), the product is $-x_k$.
- If $x_k = -128$, the product is $-(-128) = +128$.
- **Hardware requirement:** Inputs must be sign-extended to at least 9 bits signed (`[-128, +128]`) before negation and accumulated into the 32-bit adder. Storing intermediate negation in an INT8 temporary is prohibited.

### 2.2 Dimension Limits & Overflow Contract
- **Supported dimensions:** $1 \le K, M \le 4096$.
- **Conservative safety condition:**
  $$|\text{bias}_m| + 128 \times K \le 2,147,483,647$$
- The offline exporter checks this condition.
- If malformed data causes an intermediate or final accumulation overflow beyond the 32-bit signed range in hardware, the engine asserts `ERROR_ARITHMETIC_OVERFLOW` and halts rather than producing corrupted predictions.

---

## 3. Output Scaling & Requantization

Talos 2 supports two output modes: **Raw INT32 Mode** (for bring-up and debugging) and **Quantized INT8 Mode** (standard layer execution).

### 3.1 Raw INT32 Mode (`flag_raw == 1`)
- The 32-bit signed accumulator $\text{acc}_m$ is written directly to memory in little-endian format (4 bytes per output).

### 3.2 Quantized INT8 Mode (`flag_raw == 0`)
Each output channel has two scaling parameters:
- `multiplier`: Unsigned 16-bit integer (`UINT16`, range `0` to `65535`).
- `shift`: Unsigned 8-bit integer (`UINT8`, range `0` to `31`).

#### Intermediate Product
$$P = \text{acc}_m \times \text{multiplier}$$
$P$ is a signed 48-bit integer. If $\text{multiplier} = 0$, $P = 0$.

#### Rounding: Ties Away from Zero
- For $\text{shift} = 0$:
  $$Q = P$$
- For $\text{shift} > 0$:
  Let $H = 1 \ll (\text{shift} - 1)$.
  $$Q = \begin{cases} (P + H) \gg \text{shift} & \text{if } P \ge 0 \\ -((-P + H) \gg \text{shift}) & \text{if } P < 0 \end{cases}$$
  *(Note: $\gg$ denotes logical right shift on positive values).*

#### Optional ReLU (`flag_relu == 1`)
$$R = \begin{cases} \max(0, Q) & \text{if flag\_relu} = 1 \\ Q & \text{otherwise} \end{cases}$$

#### INT8 Saturation
$$Y = \text{clamp}(R, -128, +127)$$
$Y$ is written to the output destination as a signed INT8 byte.

---

## 4. Packing & Memory Layout Candidates

1. **Weight Tiles:**
   - Tile size: $4 \text{ outputs} \times 64 \text{ inputs} = 256 \text{ weights} = 64 \text{ bytes}$.
   - Pack order: 4 consecutive weights per byte, lowest 2 bits first:
     $$\text{byte} = (w_0 \& 3) \mid ((w_1 \& 3) \ll 2) \mid ((w_2 \& 3) \ll 4) \mid ((w_3 \& 3) \ll 6)$$
   - Stored in output-block order ($rb$), then input-block order ($kb$).
   - Incomplete row/column blocks are zero-padded (`2'b00`).
2. **Buffer / Accumulator Starting Candidates:**
   - Input buffer: 64 bytes.
   - Partial sums: 4 parallel INT32 accumulators.
   - *(Note: Subject to 2×2 tile area gate; fallback is 32-byte buffer / 1 accumulator).*
