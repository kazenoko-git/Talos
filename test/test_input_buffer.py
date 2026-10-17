"""
COCOTB TESTBENCH FOR THE INPUT_BUFFER MODULE
"""

from pathlib import Path
import random
import pytest
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge
from cocotb_tools.runner import get_runner

async def init_buffer(dut):
    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())
    dut.rst_n.value = 0
    dut.wr_en.value = 0
    dut.wr_addr.value = 0
    dut.wr_data.value = 0
    dut.rd_addr.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

@cocotb.test()
async def test_reset_state(dut): # verify reset zeroes all 64 buffer locations
    await init_buffer(dut)
    for addr in range(64):
        dut.rd_addr.value = addr
        await FallingEdge(dut.clk)
        assert dut.rd_data.value.to_unsigned() == 0

@cocotb.test()
async def test_sequential_write_and_read(dut):
    await init_buffer(dut)
    test_data = [random.randint(0, 255) for _ in range(64)]

    # Write all 64 bytes
    dut.wr_en.value = 1
    for addr in range(64):
        dut.wr_addr.value = addr
        dut.wr_data.value = test_data[addr]
        await RisingEdge(dut.clk)
    dut.wr_en.value = 0
    await FallingEdge(dut.clk)

    # Read back and compare
    for addr in range(64):
        dut.rd_addr.value = addr
        await FallingEdge(dut.clk)
        assert dut.rd_data.value.to_unsigned() == test_data[addr]

def test_input_buffer_runner():
    test_dir = Path(__file__).resolve().parent
    root_dir = test_dir.parent
    sim_build = test_dir / "sim_build" / "input_buffer"

    runner = get_runner("icarus")
    runner.build(
        sources=[
            root_dir / "src" / "input_buffer.v",
            test_dir / "tb_input_buffer.v",
        ],
        hdl_toplevel="tb_input_buffer",
        always=True,
        build_dir=sim_build
    )
    runner.test(
        test_module="test_input_buffer",
        hdl_toplevel="tb_input_buffer",
        build_dir=sim_build,
        test_dir=test_dir
    )
