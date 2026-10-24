"""
Unit tests for Talos 2 reference oracle and packed tiled execution.
"""
import pytest
from software.reference.oracle import (
    round_ties_away_from_zero,
    quantize_output,
    reference_dense_layer,
)
from software.reference.packing import pack_weights_tiled, unpack_and_execute_tiled


def test_round_ties_away_from_zero():
    # Positive half-way ties
    assert round_ties_away_from_zero(1, 1) == 1   # +0.5 -> +1
    assert round_ties_away_from_zero(3, 1) == 2   # +1.5 -> +2
    assert round_ties_away_from_zero(2, 1) == 1   # +1.0 -> +1

    # Negative half-way ties
    assert round_ties_away_from_zero(-1, 1) == -1  # -0.5 -> -1
    assert round_ties_away_from_zero(-3, 1) == -2  # -1.5 -> -2
    assert round_ties_away_from_zero(-2, 1) == -1  # -1.0 -> -1

    # Shift 0
    assert round_ties_away_from_zero(42, 0) == 42
    assert round_ties_away_from_zero(-42, 0) == -42


def test_extreme_negation_boundary():
    # Input -128 with weight -1 must produce acc = +128
    res = reference_dense_layer(inputs=[-128], weights=[[-1]], biases=[0], raw_mode=True)
    assert res[0] == 128


def test_invalid_weight_code():
    # 2'b11 code triggers an error
    bad_tile = bytearray(64)
    bad_tile[0] = 0b00000011  # lowest bit pair is 2'b11
    with pytest.raises(ValueError, match="Invalid weight code"):
        unpack_and_execute_tiled(
            inputs=[10],
            packed_weights=bytes(bad_tile),
            M=1,
            K=1,
            biases=[0],
            raw_mode=True,
        )


def test_5x65_tail_dimensions_exact_agreement():
    # 5 outputs (M % 4 = 1) x 65 inputs (K % 64 = 1)
    M = 5
    K = 65
    inputs = [-128 if i % 9 == 0 else (i % 255 - 128) for i in range(K)]
    weights = [[(i + j) % 3 - 1 for i in range(K)] for j in range(M)]
    biases = [500 * (j + 1) for j in range(M)]
    multipliers = [12000 + j * 4000 for j in range(M)]
    shifts = [8 + j for j in range(M)]

    # 1. Raw mode comparison
    oracle_raw = reference_dense_layer(inputs, weights, biases, raw_mode=True)
    packed = pack_weights_tiled(weights)
    assert len(packed) == 2 * 2 * 64  # 4 tiles = 256 bytes

    packed_raw = unpack_and_execute_tiled(inputs, packed, M, K, biases, raw_mode=True)
    assert oracle_raw == packed_raw

    # 2. Quantized mode with ReLU
    oracle_q = reference_dense_layer(inputs, weights, biases, multipliers, shifts, relu=True)
    packed_q = unpack_and_execute_tiled(
        inputs, packed, M, K, biases, multipliers, shifts, relu=True
    )
    assert oracle_q == packed_q
