"""
Tiled Weight Packing and the Hardware Execution Emulation
"""

import math
from typing import List, Optional
from software.reference.oracle import quantize_output

def pack_weights_tiled(weights: List[List[int]]) -> bytes:
    """
    Pack ternary weight matrix of shape (M, K) into tiled bytes.
    The tile geometry - 4 rows (outputs) x 64 columns (inputs) - so 64 bytes.
    """

    M = len(weights)
    K = len(weights[0])
    num_rb = math.ceil(M/4)
    num_kb = math.ceil(K / 64)

    tile_bytes = bytearray()

    for rb in range(num_rb):
        for kb in range(num_kb):
            tile = bytearray(64)
            for r in range(4):
                row_idx = rb*4 + r
                for c_byte in range(16):
                    b = 0
                    for bit_pair in range(4):
                        col_idx = kb*64 + c_byte*4 + bit_pair
                        if row_idx < M and col_idx < K:
                            w = weights[row_idx][col_idx]
                            if w == 0: code = 0b00
                            elif w == 1: code = 0b01
                            elif w == -1: code = 0b10
                            else: raise ValueError(f"Invalid weight: {w}")
                        else: code = 0b00 # zero padding

                        # pack lowest two bits first
                        b |= code << (bit_pair * 2)
                    tile[r * 16 + c_byte] = b
            tile_bytes.extend(tile)

    return bytes(tile_bytes)


def unpack_and_execute_tiled(
    inputs: List[int],
    packed_weights: bytes,
    M: int,
    K: int,
    biases: List[int],
    multipliers: Optional[List[int]] = None,
    shifts: Optional[List[int]] = None,
    relu: bool = False,
    raw_mode: bool = False,
) -> List[int]:
    """
    Simulate hardware execution using tiled packed weights and 4 partial sums.
    """
    num_rb = math.ceil(M / 4)
    num_kb = math.ceil(K / 64)
    expected_size = num_rb * num_kb * 64
    assert len(packed_weights) == expected_size, (
        f"Tile buffer length {len(packed_weights)} != expected {expected_size}"
    )

    code_to_val = {0b00: 0, 0b01: 1, 0b10: -1}
    results = []

    for rb in range(num_rb):
        valid_m = min(4, M - rb * 4)
        # Initialize 4 partial sums with bias (applied once before first input chunk)
        accs = [biases[rb * 4 + r] if r < valid_m else 0 for r in range(4)]

        for kb in range(num_kb):
            tile_offset = (rb * num_kb + kb) * 64
            tile = packed_weights[tile_offset : tile_offset + 64]

            # Stream weights across the 4 partial sums
            for r in range(valid_m):
                row_slice = tile[r * 16 : (r + 1) * 16]
                for c_byte in range(16):
                    b = row_slice[c_byte]
                    for bit_pair in range(4):
                        k_idx = kb * 64 + c_byte * 4 + bit_pair
                        if k_idx < K:
                            code = (b >> (bit_pair * 2)) & 0b11
                            if code == 0b11:
                                raise ValueError("Hardware error: Invalid weight code 2'b11")
                            w = code_to_val[code]
                            x = inputs[k_idx]
                            if w == 1:
                                accs[r] += x
                            elif w == -1:
                                accs[r] -= x

        # Scale and write back valid outputs for this row block
        for r in range(valid_m):
            m = rb * 4 + r
            if raw_mode:
                results.append(accs[r])
            else:
                results.append(quantize_output(accs[r], multipliers[m], shifts[m], relu))

    return results
