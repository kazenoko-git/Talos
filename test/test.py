# SPDX-FileCopyrightText: © 2026 Ivan
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

def set_cs(dut, active: bool):
    current = int(dut.ui_in.value)
    if active:
        dut.ui_in.value = current & ~(1 << 2)  # cs_n = 0
    else:
        dut.ui_in.value = current | (1 << 2)   # cs_n = 1

async def spi_transfer_byte(dut, tx_byte):
    """Transfers 1 byte over SPI Mode 0 and returns received byte."""
    rx_byte = 0
    for bit in range(7, -1, -1):
        # Set MOSI while SCLK is low
        current = int(dut.ui_in.value)
        mosi_bit = (tx_byte >> bit) & 1
        dut.ui_in.value = (current & ~0x02) | (mosi_bit << 1)
        await ClockCycles(dut.clk, 4)
        
        # SCLK Rising Edge: Slave samples MOSI, Master samples MISO
        dut.ui_in.value = int(dut.ui_in.value) | 0x01
        await ClockCycles(dut.clk, 4)
        miso_bit = (int(dut.uo_out.value) >> 0) & 1
        rx_byte = (rx_byte << 1) | miso_bit
        
        # SCLK Falling Edge: Slave updates MISO
        dut.ui_in.value = int(dut.ui_in.value) & ~0x01
        await ClockCycles(dut.clk, 4)
        
    return rx_byte

async def spi_write_reg(dut, addr, value):
    """Writes 1 byte to a specific register."""
    set_cs(dut, True)
    await ClockCycles(dut.clk, 8)
    await spi_transfer_byte(dut, addr & 0x7F)
    await spi_transfer_byte(dut, value & 0xFF)
    await ClockCycles(dut.clk, 8)
    set_cs(dut, False)
    await ClockCycles(dut.clk, 16)

async def spi_read_reg(dut, addr):
    """Reads 1 byte from a specific register."""
    set_cs(dut, True)
    await ClockCycles(dut.clk, 8)
    await spi_transfer_byte(dut, 0x80 | (addr & 0x7F))
    val = await spi_transfer_byte(dut, 0x00)
    await ClockCycles(dut.clk, 8)
    set_cs(dut, False)
    await ClockCycles(dut.clk, 16)
    return val

async def spi_stream_compute(dut, activations, weights):
    """Streams 32 activations and 32 weights to Port 0x10."""
    set_cs(dut, True)
    await ClockCycles(dut.clk, 8)
    await spi_transfer_byte(dut, 0x10)  # Stream Port Address
    
    # Send 32 Activations (Bytes 0 to 31)
    for a in activations:
        await spi_transfer_byte(dut, a & 0xFF)
        
    # Send 32 Weights (Bytes 32 to 63)
    for w in weights:
        # Ternary encoding: 0 -> 2'b00, +1 -> 2'b01, -1 -> 2'b11 (0x03)
        if w == 1:
            code = 0x01
        elif w == -1:
            code = 0x03
        else:
            code = 0x00
        await spi_transfer_byte(dut, code)
        
    await ClockCycles(dut.clk, 8)
    set_cs(dut, False)
    await ClockCycles(dut.clk, 16)

async def spi_read_accumulator(dut):
    """Reads 24-bit accumulator value from registers 0x02, 0x03, 0x04."""
    low = await spi_read_reg(dut, 0x02)
    mid = await spi_read_reg(dut, 0x03)
    high = await spi_read_reg(dut, 0x04)
    val = (high << 16) | (mid << 8) | low
    if val & 0x800000:
        val -= 0x1000000
    return val

async def reset_dut(dut):
    clock = Clock(dut.clk, 62.5, unit="ns") # 16 MHz
    cocotb.start_soon(clock.start())
    dut.ena.value = 1
    dut.ui_in.value = 0x04 # CS_n=1, SCLK=0, MOSI=0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 10)

@cocotb.test()
async def test_full_neuromorphic_npu(dut):
    """Comprehensive End-to-End Test for Talos Neuromorphic Micro-NPU"""
    await reset_dut(dut)
    
    # -------------------------------------------------------------
    # 1. SPI Sanity Check
    # -------------------------------------------------------------
    dut._log.info("=== Step 1: SPI Register Read/Write Sanity Check ===")
    await spi_write_reg(dut, 0x00, 0x08) # Set act_en=1
    ctrl_val = await spi_read_reg(dut, 0x00)
    dut._log.info(f"Read back Control Register: {hex(ctrl_val)}")
    assert ctrl_val == 0x08, f"Expected 0x08, got {hex(ctrl_val)}"
    
    # -------------------------------------------------------------
    # 2. BitNet b1.58 Ternary Math Accuracy
    # -------------------------------------------------------------
    dut._log.info("=== Step 2: BitNet b1.58 Ternary Dot Product Math ===")
    await spi_write_reg(dut, 0x00, 0x01) # Reset accumulator
    
    activations = [10] * 32
    weights = [1]*16 + [0]*8 + [-1]*8 # 16*(+10) + 0 - 8*(+10) = +80
    await spi_stream_compute(dut, activations, weights)
    
    acc = await spi_read_accumulator(dut)
    dut._log.info(f"Accumulator output: {acc} (Expected: +80)")
    assert acc == 80, f"Expected 80, got {acc}"
    
    # Read Post-Activation output (Register 0x05)
    act_out = await spi_read_reg(dut, 0x05)
    dut._log.info(f"Post-Activation output (reg 0x05): {act_out} (Expected: 80)")
    assert act_out == 80, f"Expected 80, got {act_out}"
    
    # -------------------------------------------------------------
    # 3. Chained Multi-Chunk Accumulation and Reset
    # -------------------------------------------------------------
    dut._log.info("=== Step 3: Chained Multi-Chunk Accumulation ===")
    activations2 = [5] * 32
    weights2 = [1] * 32 # 32 * 5 = +160. Total: 80 + 160 = 240!
    await spi_stream_compute(dut, activations2, weights2)
    
    acc2 = await spi_read_accumulator(dut)
    dut._log.info(f"Chained Accumulator: {acc2} (Expected: +240)")
    assert acc2 == 240, f"Expected 240, got {acc2}"
    
    # Test accumulator reset via SPI
    await spi_write_reg(dut, 0x00, 0x01) # rst_acc = 1
    acc_reset = await spi_read_accumulator(dut)
    dut._log.info(f"Accumulator after reset: {acc_reset} (Expected: 0)")
    assert acc_reset == 0, f"Expected 0, got {acc_reset}"
    
    # -------------------------------------------------------------
    # 4. 1-Bit Binary Neural Network (BNN Mode)
    # -------------------------------------------------------------
    dut._log.info("=== Step 4: 1-Bit BNN Mode (XNOR Popcount) ===")
    await spi_write_reg(dut, 0x00, 0x02) # Mode = 01 (BNN)
    
    activations_bnn = [1] * 32
    weights_bnn = [1] * 32 # 1 XNOR 1 = +1 for all 32 lanes -> sum = +32
    await spi_stream_compute(dut, activations_bnn, weights_bnn)
    
    acc_bnn = await spi_read_accumulator(dut)
    dut._log.info(f"BNN Accumulator: {acc_bnn} (Expected: +32)")
    assert acc_bnn == 32, f"Expected 32, got {acc_bnn}"
    
    # -------------------------------------------------------------
    # 5. Fused ReLU and Clamp Function
    # -------------------------------------------------------------
    dut._log.info("=== Step 5: Fused ReLU and Clamping ===")
    # Reset accumulator, Mode = 00 (BitNet), act_en = 1 (bit 3) -> 0x09
    await spi_write_reg(dut, 0x00, 0x09)
    
    activations_neg = [10] * 32
    weights_neg = [-1] * 32 # 32 * -10 = -320
    await spi_stream_compute(dut, activations_neg, weights_neg)
    
    acc_neg = await spi_read_accumulator(dut)
    dut._log.info(f"Raw Negative Accumulator: {acc_neg} (Expected: -320)")
    assert acc_neg == -320, f"Expected -320, got {acc_neg}"
    
    # Check that fused ReLU clamps negative to 0 on reg 0x05
    act_neg = await spi_read_reg(dut, 0x05)
    dut._log.info(f"Post-ReLU Output: {act_neg} (Expected: 0)")
    assert act_neg == 0, f"Expected ReLU output 0, got {act_neg}"
    
    dut._log.info("*** ALL TALOS TESTS COMPLETED SUCCESSFULLY! ***")
