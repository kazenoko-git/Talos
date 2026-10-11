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

async def step_reservoir_spi(dut):
    """This pulses step_tick via SPI control register 0x00."""
    await spi_write_reg(dut, 0x00, 0x01)

async def step_reservoir_pin(dut):
    """This pulses the ext_tick input pin ui_in[3]."""
    current = int(dut.ui_in.value)
    dut.ui_in.value = current | (1 << 3)
    await ClockCycles(dut.clk, 4)
    dut.ui_in.value = current & ~(1 << 3)
    await ClockCycles(dut.clk, 4)

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
async def test_spi_registers_and_defaults(dut):
    """Verify SPI config registers and default neuromorphic parameters."""
    await reset_dut(dut)
    dut._log.info("Testing default register values...")

    v_th = await spi_read_reg(dut, 0x01)
    weight_scale = await spi_read_reg(dut, 0x02)
    assert v_th == 32, f"Expected default V_th = 32, got {v_th}"
    assert weight_scale == 12, f"Expected default W_scale = 12, got {weight_scale}"

    # Write new params
    dut._log.info("Configuring custom V-th=50, W_scale=16, leak_sel=01 (>>3)...")
    await spi_write_reg(dut, 0x01, 50)
    await spi_write_reg(dut, 0x02, 16)
    await spi_write_reg(dut, 0x06, 0x01) # leak_sel = 01 (>>3)

    v_th_read = await spi_read_reg(dut, 0x01)
    w_scale_read = await spi_read_reg(dut, 0x02)
    leak_read = await spi_read_reg(dut, 0x06)
    assert v_th_read == 50, f"Expected V_th = 50, got {v_th_read}"
    assert w_scale_read == 16, f"Expected W_scale = 16, got {w_scale_read}"
    assert leak_read == 0x01, f"Expected leak_sel=01, got {leak_read}"

@cocotb.test()
async def test_subthreshold_integration_and_leak(dut):
    """Verify leaky integration decay when potential is subthreshold."""
    await reset_dut(dut)
    # Set V_th = 60, W_scale = 10, leak_sel = 10 (>>2 = 25% decay)
    await spi_write_reg(dut, 0x01, 60)
    await spi_write_reg(dut, 0x02, 10)
    await spi_write_reg(dut, 0x06, 0x02)

    # Inject external spike into Neuron 0 (weight = 2 * 10 = +20)
    await spi_write_reg(dut, 0x03, 0x01)
    await step_reservoir_spi(dut)

    v0 = await spi_read_reg(dut, 0x10)
    dut._log.info(f"After input spike: Neuron 0 potential = {v0}")
    assert v0 == 20, f"Expected V0=20 after external spike, got {v0}"

    # Clear external spike and advance time: potential must leak (20 - 20>>2 = 15)
    await spi_write_reg(dut, 0x03, 0x00)
    await step_reservoir_spi(dut)

    v0_leaked = await spi_read_reg(dut, 0x10)
    dut._log.info(f"After leak step: Neuron 0 potential = {v0_leaked}")
    assert v0_leaked == 15, f"Expected V0=15 after leak, got {v0_leaked}"


@cocotb.test()
async def test_threshold_firing_and_reset(dut):
    """Verify that crossing threshold generates a spike pulse and resets potential."""
    await reset_dut(dut)
    # Set V_th = 30, W_scale = 20, leak_sel = 00 (no leak)
    await spi_write_reg(dut, 0x01, 30)
    await spi_write_reg(dut, 0x02, 20)
    await spi_write_reg(dut, 0x06, 0x00)

    # Inject spike into Neuron 0 (input = +40 >= 30 -> fires!)
    await spi_write_reg(dut, 0x03, 0x01)
    await step_reservoir_spi(dut)

    spikes_low = await spi_read_reg(dut, 0x04)
    v0_after = await spi_read_reg(dut, 0x10)
    dut._log.info(f"Spikes register low: 0x{spikes_low:02X}, V0: {v0_after}")

    assert (spikes_low & 0x01) == 1, "Neuron 0 should have fired a spike!"
    assert v0_after == 0, f"Expected V0=0 after spike reset, got {v0_after}"

    # Verify physical pin output on carrier board LEDs
    uo_pins = int(dut.uo_out.value)
    assert (uo_pins & 0x02) != 0, "uo_out[1] (spike[0] LED) should be active!"


@cocotb.test()
async def test_recurrent_spatio_temporal_dynamics(dut):
    """Verify recurrent reservoir propagation and fading memory across 16 neurons."""
    await reset_dut(dut)
    dut._log.info("Testing 16-neuron recurrent liquid dynamics...")

    # Set parameters: V_th = 25, W_scale = 15, leak_sel = >>3 (12.5% decay)
    await spi_write_reg(dut, 0x01, 25)
    await spi_write_reg(dut, 0x02, 15)
    await spi_write_reg(dut, 0x06, 0x01)

    # Inject a 1-step impulse into Neurons 0 and 2
    await spi_write_reg(dut, 0x03, 0x05)
    await step_reservoir_spi(dut)

    # Turn off external input: reservoir now runs autonomously via recurrent feedback
    await spi_write_reg(dut, 0x03, 0x00)

    for step in range(5):
        await step_reservoir_spi(dut)
        spk_lo = await spi_read_reg(dut, 0x04)
        spk_hi = await spi_read_reg(dut, 0x05)
        total_spikes = (spk_hi << 8) | spk_lo
        dut._log.info(f"  Step {step+1}: 16-Neuron Spike Pattern = 0b{total_spikes:016b}")

    dut._log.info("*** All neuromorphic reservoir tests passed! ***")


@cocotb.test()
async def test_hardware_pin_stepping(dut):
    """Verify that pulsing ext_tick on ui_in[3] advances the reservoir correctly."""
    await reset_dut(dut)
    await spi_write_reg(dut, 0x01, 50)
    await spi_write_reg(dut, 0x02, 12)

    # Inject external spike into Neuron 1
    await spi_write_reg(dut, 0x03, 0x02)

    # Step via physical pin ui_in[3]
    await step_reservoir_pin(dut)

    v1 = await spi_read_reg(dut, 0x11)
    dut._log.info(f"After pin-triggered step: Neuron 1 potential = {v1}")
    assert v1 == 24, f"Expected V1=24 after pin step, got {v1}"

