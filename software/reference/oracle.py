"""
Bit-exact reference implementation for a dense ternary layer execution.
"""

from typing import List, Optional

INT32_MIN = -2147483648
INT32_MAX = 2147483647

def round_ties_away_from_zero(prod: int, shift: int) -> int:
    if shift == 0: return prod
    half = 1 << (shift - 1)      # half the divisor
    if prod >= 0: return (prod + half) >> shift
    else: return -((-prod + half) >> shift)

# Backward-compatibility alias for previous typo
round_tiles_away_from_zero = round_ties_away_from_zero

def quantize_output(acc: int, multiplier: int, shift: int, relu: bool) -> int:
    """
    Scale the accumulator by UINT16 multiplier, shift, apply optional ReLU and saturate to INT8.
    """
    assert 0 <= multiplier <= 65535, f"Multiplier {multiplier} outside UINT16 range"
    assert 0 <= shift <= 31, f"Shift {shift} outside [0,31] range"

    if multiplier == 0: val = 0
    else: 
        prod = acc * multiplier 
        val = round_ties_away_from_zero(prod, shift)
    
    if relu: val = max(0, val)

    # saturate to signed INT8
    return max(-128, min(127, val))

def reference_dense_layer(
    inputs: List[int],
    weights: List[List[int]],
    biases: List[int],
    multipliers: Optional[List[int]] = None,
    shifts: Optional[List[int]] = None,
    relu: bool = False,
    raw_mode: bool = False
) -> List[int]:
    """
    Bit-exact reference dense layer eval.
    These are the expected formats.
    inputs: shape (K,), values in [-128, 127]
    weights: shape (M, K, ), values in {-1, 0 +1}
    biases: shape (M, ), signed INT32
    """

    M = len(weights)
    K = len(inputs)
    assert 1 <= M <= 4096, f"M={M} outside supported bounds [1, 4096]"
    assert 1 <= K <= 4096, f"K={K} outside supported bounds [1, 4096]"
    assert len(biases) == M, f"Biases length {len(biases)} != M={M}"
    if not raw_mode:
        assert multipliers is not None and len(multipliers) == M
        assert shifts is not None and len(shifts) == M
    outputs = []
    for m in range(M):
        # Exporter safety bound check
        assert abs(biases[m]) + 128 * K <= INT32_MAX, (f"Output {m} violates conservative INT32 bound")
        # Apply bias once per output before first input chunk
        acc = biases[m]
        for k in range(K):
            x = inputs[k]
            assert -128 <= x <= 127, f"Input {x} at index {k} out of INT8 range"
            w = weights[m][k]
            if w == 1:
                acc += x
            elif w == -1:
                # Sign extension ensures -(-128) becomes +128 without INT8 overflow
                acc -= x
            elif w == 0: pass
            else: raise ValueError(f"Invalid weight {w} at ({m}, {k})")
        assert INT32_MIN <= acc <= INT32_MAX, f"Accumulator overflow: {acc}"
        if raw_mode: outputs.append(acc)
        else: outputs.append(quantize_output(acc, multipliers[m], shifts[m], relu))
    return outputs