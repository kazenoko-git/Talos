"""
Verifies reset, bias loading, ternary decoding, boundary negation, overflow, and oracle agreement using cocotb
"""
from pathlib import Path
import random
import pytest
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge
from cocotb_tools.runner import get_runner


async def init_test(dut):
    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())
    dut.rst_n.value = 0
    dut.clear_acc.value = 0
    dut.load_bias.value = 0
    dut.initial_bias.value = 0
    dut.en.value = 0
    dut.weight_code.value = 0
    dut.data_in.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


@cocotb.test()
async def test_reset_and_bias(dut):
    # Test reset state and loading initial signed INT32 bias.
    await init_test(dut)

    assert dut.acc.value.to_signed() == 0
    assert int(dut.err_invalid.value) == 0
    assert int(dut.err_overflow.value) == 0

    # Load initial negative bias
    dut.clear_acc.value = 1
    dut.load_bias.value = 1
    dut.initial_bias.value = -123456
    await RisingEdge(dut.clk)
    dut.clear_acc.value = 0
    dut.load_bias.value = 0
    await FallingEdge(dut.clk)

    assert dut.acc.value.to_signed() == -123456


@cocotb.test()
async def test_negation_boundary(dut):
    # Verify extreme boundary i.e input -128 with weight -1 yields +128 without overflow.
    await init_test(dut)

    dut.en.value = 1
    dut.weight_code.value = 0b10  # -1
    dut.data_in.value = 0x80      # -128 in 8-bit two's complement
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)

    assert dut.acc.value.to_signed() == 128
    assert int(dut.err_invalid.value) == 0
    assert int(dut.err_overflow.value) == 0

    # Accumulate again: +128 + 128 = 256
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    assert dut.acc.value.to_signed() == 256


@cocotb.test()
async def test_zero_and_positive_weights(dut):
    # Verify weight code 2'b00 (no-op) and 2'b01 (+1 add).
    await init_test(dut)

    # no change to accumulator
    dut.en.value = 1
    dut.weight_code.value = 0b00
    dut.data_in.value = 42
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    assert dut.acc.value.to_signed() == 0

    # add +42
    dut.weight_code.value = 0b01
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    assert dut.acc.value.to_signed() == 42


@cocotb.test()
async def test_invalid_weight_code(dut):
    # Verify 2'b11 code asserts err_invalid flag and does not modify acc.
    await init_test(dut)

    dut.en.value = 1
    dut.weight_code.value = 0b11  # Invalid code
    dut.data_in.value = 50
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)

    assert int(dut.err_invalid.value) == 1
    assert dut.acc.value.to_signed() == 0


@cocotb.test()
async def test_overflow_detection(dut):
    # Verify signed 32-bit overflow flag assertion.
    await init_test(dut)

    # Pre-load INT32_MAX = 2147483647
    dut.clear_acc.value = 1
    dut.load_bias.value = 1
    dut.initial_bias.value = 0x7FFFFFFF
    await RisingEdge(dut.clk)
    dut.clear_acc.value = 0
    dut.load_bias.value = 0
    await FallingEdge(dut.clk)

    # Add +1 -> overflow beyond INT32_MAX
    dut.en.value = 1
    dut.weight_code.value = 0b01
    dut.data_in.value = 1
    await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)

    assert int(dut.err_overflow.value) == 1


@cocotb.test()
async def test_random_stream_vs_oracle(dut):
    # Stream 64 random inputs and verify exact agreement with expected accumulation.
    await init_test(dut)

    initial_bias = 500
    dut.clear_acc.value = 1
    dut.load_bias.value = 1
    dut.initial_bias.value = initial_bias
    await RisingEdge(dut.clk)
    dut.clear_acc.value = 0
    dut.load_bias.value = 0
    await FallingEdge(dut.clk)

    expected_acc = initial_bias
    dut.en.value = 1

    for _ in range(64):
        # Pick random INT8 and valid weight in {-1, 0, +1}
        x = random.randint(-128, 127)
        w = random.choice([-1, 0, 1])
        w_code = {0: 0b00, 1: 0b01, -1: 0b10}[w]

        # Convert to unsigned 8-bit representation for Verilog driving
        x_u8 = x if x >= 0 else (x + 256)
        dut.weight_code.value = w_code
        dut.data_in.value = x_u8

        expected_acc += (w * x)

        await RisingEdge(dut.clk)
        await FallingEdge(dut.clk)

    assert dut.acc.value.to_signed() == expected_acc
    assert int(dut.err_invalid.value) == 0
    assert int(dut.err_overflow.value) == 0


def test_ternary_pe_runner():
    # Pytest entrypoint to compile and run cocotb simulation via Icarus.
    test_dir = Path(__file__).resolve().parent
    root_dir = test_dir.parent
    sim_build = test_dir / "sim_build" / "ternary_pe"

    runner = get_runner("icarus")
    runner.build(
        sources=[
            root_dir / "src" / "ternary_pe.v",
            test_dir / "tb_ternary_pe.v",
        ],
        hdl_toplevel="tb_ternary_pe",
        always=True,
        build_dir=sim_build,
    )
    runner.test(
        hdl_toplevel="tb_ternary_pe",
        test_module="test_ternary_pe",
        test_dir=test_dir,
        build_dir=sim_build,
    )
