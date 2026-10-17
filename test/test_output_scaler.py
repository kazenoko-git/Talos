"""
OUTPUT SCALER COCOTB TESTBENCH

This verifies symmetric rounding ties away from zero, shift=0, multiplier=0, optional ReLU, INT8 saturation clamp, raw mode, and randomized oracle equivalence.
"""
from pathlib import Path
import random
import pytest
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge
from cocotb_tools.runner import get_runner

from software.reference.oracle import quantize_output


async def init_scaler(dut):
    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())
    dut.rst_n.value = 0
    dut.start.value = 0
    dut.raw_mode.value = 0
    dut.relu.value = 0
    dut.acc.value = 0
    dut.multiplier.value = 0
    dut.shift.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def scale_op(dut, acc: int, multiplier: int, shift: int, relu: int, raw_mode: int = 0):
    dut.acc.value = acc
    dut.multiplier.value = multiplier
    dut.shift.value = shift
    dut.relu.value = relu
    dut.raw_mode.value = raw_mode
    dut.start.value = 1
    await RisingEdge(dut.clk)
    dut.start.value = 0

    # Await done signal
    while not dut.done.value:
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)

    return dut.data_out_int8.value.to_signed(), dut.data_out_raw.value.to_signed()


@cocotb.test()
async def test_rounding_ties(dut):
    # Verify symmetric round-half-away-from-zero for both positive and negative values.
    await init_scaler(dut)

    # Positive half-way ties: 3 / 2 = +1.5 -> +2
    res_int8, _ = await scale_op(dut, acc=3, multiplier=1, shift=1, relu=0)
    assert res_int8 == 2, f"Expected 2, got {res_int8}"

    # Positive half-way ties: 1 / 2 = +0.5 -> +1
    res_int8, _ = await scale_op(dut, acc=1, multiplier=1, shift=1, relu=0)
    assert res_int8 == 1, f"Expected 1, got {res_int8}"

    # Non-halfway: 2 / 2 = +1.0 -> +1
    res_int8, _ = await scale_op(dut, acc=2, multiplier=1, shift=1, relu=0)
    assert res_int8 == 1, f"Expected 1, got {res_int8}"

    # Negative half-way ties: -3 / 2 = -1.5 -> -2
    res_int8, _ = await scale_op(dut, acc=-3, multiplier=1, shift=1, relu=0)
    assert res_int8 == -2, f"Expected -2, got {res_int8}"

    # Negative half-way ties: -1 / 2 = -0.5 -> -1
    res_int8, _ = await scale_op(dut, acc=-1, multiplier=1, shift=1, relu=0)
    assert res_int8 == -1, f"Expected -1, got {res_int8}"

    # Negative non-halfway: -2 / 2 = -1.0 -> -1
    res_int8, _ = await scale_op(dut, acc=-2, multiplier=1, shift=1, relu=0)
    assert res_int8 == -1, f"Expected -1, got {res_int8}"


@cocotb.test()
async def test_relu_and_saturation(dut):
    # verify ReLU activation and signed INT8 [-128, +127] saturation.
    await init_scaler(dut)

    # Negative value with ReLU disabled -> passes negative INT8
    res_int8, _ = await scale_op(dut, acc=-50, multiplier=1, shift=0, relu=0)
    assert res_int8 == -50

    # Negative value with ReLU enabled -> clamped to 0
    res_int8, _ = await scale_op(dut, acc=-50, multiplier=1, shift=0, relu=1)
    assert res_int8 == 0

    # Positive value with ReLU enabled -> remains positive
    res_int8, _ = await scale_op(dut, acc=50, multiplier=1, shift=0, relu=1)
    assert res_int8 == 50

    # Positive saturation beyond +127 -> clamps to +127
    res_int8, _ = await scale_op(dut, acc=500, multiplier=1, shift=0, relu=0)
    assert res_int8 == 127

    # Negative saturation below -128 -> clamps to -128
    res_int8, _ = await scale_op(dut, acc=-500, multiplier=1, shift=0, relu=0)
    assert res_int8 == -128


@cocotb.test()
async def test_zero_multiplier_and_shift(dut):
    # Verify edge cases: multiplier zero produces zero, shift zero has no rounding.
    await init_scaler(dut)

    # Multiplier zero -> always 0
    res_int8, _ = await scale_op(dut, acc=12345, multiplier=0, shift=5, relu=0)
    assert res_int8 == 0

    # Shift zero -> direct product acc * mult clamped to INT8
    res_int8, _ = await scale_op(dut, acc=25, multiplier=3, shift=0, relu=0)
    assert res_int8 == 75


@cocotb.test()
async def test_raw_mode_bypass(dut):
    # Verify raw_mode bypass passes raw INT32 accumulator to data_out_raw.
    await init_scaler(dut)

    test_acc = -123456789
    _, res_raw = await scale_op(dut, acc=test_acc, multiplier=1000, shift=4, relu=0, raw_mode=1)
    assert res_raw == test_acc


@cocotb.test()
async def test_random_vs_oracle(dut):
    # Stream 100 randomized cases and verify bit-exact agreement against oracle.
    await init_scaler(dut)

    for _ in range(100):
        acc = random.randint(-50000, 50000)
        mult = random.randint(0, 65535)
        shift = random.randint(0, 31)
        relu = random.choice([0, 1])

        expected = quantize_output(acc, mult, shift, bool(relu))
        got_int8, got_raw = await scale_op(dut, acc, mult, shift, relu)

        assert got_int8 == expected, (
            f"Mismatch for acc={acc}, mult={mult}, shift={shift}, relu={relu}: "
            f"got {got_int8}, expected {expected}"
        )
        assert got_raw == acc


def test_output_scaler_runner():
    test_dir = Path(__file__).resolve().parent
    root_dir = test_dir.parent
    sim_build = test_dir / "sim_build" / "output_scaler"

    runner = get_runner("icarus")
    runner.build(
        sources=[
            root_dir / "src" / "output_scaler.v",
            test_dir / "tb_output_scaler.v",
        ],
        hdl_toplevel="tb_output_scaler",
        always=True,
        build_dir=sim_build,
    )
    runner.test(
        hdl_toplevel="tb_output_scaler",
        test_module="test_output_scaler",
        test_dir=test_dir,
        build_dir=sim_build,
    )
