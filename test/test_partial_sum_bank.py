"""
COCOTB TESTBENCH FOR PARTIAL SUM BANK MODULE
"""

from pathlib import Path
import random, pytest, cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge
from cocotb_tools.runner import get_runner

async def init_bank(dut):
    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())
    dut.rst_n.value = 0
    dut.wr_en.value = 0
    dut.wr_sel.value = 0
    dut.wr_data.value = 0
    dut.clear_all.value = 0
    dut.rd_sel.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

@cocotb.test()
async def test_bank_write_and_read(dut):
    # write individual channels and verify multiplexed + parallel readouts
    await init_bank(dut)

    values = [-100000, 250000, -1, 12345678]

    # write each register
    dut.wr_en.value = 1
    for sel in range(4):
        dut.wr_sel.value = sel
        dut.wr_data.value = values[sel]
        await RisingEdge(dut.clk)
    dut.wr_en.value = 0
    await FallingEdge(dut.clk)

    # check parallel logs
    assert dut.sum0.value.to_signed() == values[0]
    assert dut.sum1.value.to_signed() == values[1]
    assert dut.sum2.value.to_signed() == values[2]
    assert dut.sum3.value.to_signed() == values[3]

    # check multiplexed rd_data
    for sel in range(4):
        dut.rd_sel.value = sel
        await FallingEdge(dut.clk)
        assert dut.rd_data.value.to_signed() == values[sel]

@cocotb.test()
async def test_clear_all(dut):
    # verify sync clear_all zeroes all 4 channels
    await init_bank(dut)

    # write non zero values
    dut.wr_en.value = 1
    for sel in range(4):
        dut.wr_sel.value = sel
        dut.wr_data.value = 9999
        await RisingEdge(dut.clk)
    dut.wr_en.value = 0

    # pulse clear_all
    dut.clear_all.value = 1
    await RisingEdge(dut.clk)
    dut.clear_all.value = 0
    await FallingEdge(dut.clk)

    assert dut.sum0.value.to_signed() == 0
    assert dut.sum1.value.to_signed() == 0
    assert dut.sum2.value.to_signed() == 0
    assert dut.sum3.value.to_signed() == 0

def test_partial_sum_bank_runner():
    test_dir = Path(__file__).resolve().parent
    root_dir = test_dir.parent
    sim_build = test_dir / "sim_build" / "partial_sum_bank"

    runner = get_runner("icarus")
    runner.build(
        sources=[
            root_dir / "src" / "partial_sum_bank.v",
            test_dir / "tb_partial_sum_bank.v",
        ],
        hdl_toplevel="tb_partial_sum_bank",
        build_dir=sim_build,
        always=True
    )
    runner.test(
        hdl_toplevel="tb_partial_sum_bank",
        build_dir=sim_build,
        test_dir=test_dir,
        test_module="test_partial_sum_bank"
    )
