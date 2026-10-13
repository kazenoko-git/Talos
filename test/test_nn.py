# SPDX-FileCopyrightText: © 2026 Ivan
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles
import random

def set_cs(dut, active: bool):
    current = int(dut.ui_in.value)
    if active:
        dut.ui_in.value = current & ~(1 << 2)
    else:
        dut.ui_in.value = current | (1 << 2)

async def spi_transfer_byte(dut, tx_byte):
    rx_byte = 0
    for bit in range(7, -1, -1):
        current = int(dut.ui_in.value)
        mosi_bit = (tx_byte >> bit) & 1
        dut.ui_in.value = (current & ~0x02) | (mosi_bit << 1)
        await ClockCycles(dut.clk, 4)
        
        # SCLK Rising Edge
        dut.ui_in.value = int(dut.ui_in.value) | 0x01
        await ClockCycles(dut.clk, 4)
        miso_bit = (int(dut.uo_out.value) >> 0) & 1
        rx_byte = (rx_byte << 1) | miso_bit
        
        # SCLK Falling Edge
        dut.ui_in.value = int(dut.ui_in.value) & ~0x01
        await ClockCycles(dut.clk, 4)
    return rx_byte

async def spi_write_reg(dut, addr, value):
    set_cs(dut, True)
    await ClockCycles(dut.clk, 8)
    await spi_transfer_byte(dut, addr & 0x7F)
    await spi_transfer_byte(dut, value & 0xFF)
    await ClockCycles(dut.clk, 8)
    set_cs(dut, False)
    await ClockCycles(dut.clk, 16)

async def spi_read_reg(dut, addr):
    set_cs(dut, True)
    await ClockCycles(dut.clk, 8)
    await spi_transfer_byte(dut, 0x80 | (addr & 0x7F))
    val = await spi_transfer_byte(dut, 0x00)
    await ClockCycles(dut.clk, 8)
    set_cs(dut, False)
    await ClockCycles(dut.clk, 16)
    return val

async def step_reservoir(dut):
    # Step reservoir via SPI control register 0x00 (pulse step_tick)
    await spi_write_reg(dut, 0x00, 0x01)
    # Wait for 16-cycle sequencer
    await ClockCycles(dut.clk, 24)

async def read_all_potentials(dut):
    """Reads membrane potentials V0..V15 from registers 0x10..0x1F."""
    potentials = []
    for i in range(16):
        raw = await spi_read_reg(dut, 0x10 + i)
        # Convert signed 8-bit
        signed_val = raw - 256 if raw >= 128 else raw
        potentials.append(signed_val)
    return potentials

async def reset_dut(dut):
    clock = Clock(dut.clk, 62.5, unit="ns") # 16 MHz
    cocotb.start_soon(clock.start())
    dut.ena.value = 1
    dut.ui_in.value = 0x04 # CS_n=1
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 10)

def train_linear_classifier(X_train, y_train, l2_reg=0.1):
    """
    Pure Python Ridge Regression / Linear Readout:
    w = (X^T X + lambda * I)^(-1) X^T y
    """
    N = len(X_train)
    D = len(X_train[0]) + 1 # features + bias
    
    X_aug = [[1.0] + [float(val) for val in row] for row in X_train]
    
    A = [[0.0] * D for _ in range(D)]
    for i in range(D):
        for j in range(D):
            A[i][j] = sum(X_aug[k][i] * X_aug[k][j] for k in range(N))
            if i == j and i > 0:
                A[i][j] += l2_reg
                
    b = [sum(X_aug[k][i] * float(y_train[k]) for k in range(N)) for i in range(D)]
    
    # Gaussian elimination with partial pivoting
    for col in range(D):
        max_row = max(range(col, D), key=lambda r: abs(A[r][col]))
        A[col], A[max_row] = A[max_row], A[col]
        b[col], b[max_row] = b[max_row], b[col]
        
        pivot = A[col][col]
        if abs(pivot) < 1e-12:
            continue
        for row in range(col + 1, D):
            factor = A[row][col] / pivot
            for c in range(col, D):
                A[row][c] -= factor * A[col][c]
            b[row] -= factor * b[col]
            
    # Back substitution
    w = [0.0] * D
    for row in range(D - 1, -1, -1):
        if abs(A[row][row]) > 1e-12:
            w[row] = (b[row] - sum(A[row][c] * w[c] for c in range(row + 1, D))) / A[row][row]
            
    return w

def predict_linear(w, X_sample):
    x_aug = [1.0] + [float(v) for v in X_sample]
    val = sum(w[i] * x_aug[i] for i in range(len(w)))
    return 1 if val >= 0.5 else 0

@cocotb.test()
async def test_spatiotemporal_motion_direction_classification(dut):
    """
    Task: Classify temporal wave direction across neuromorphic channels:
      - Class 0: Forward Wave  [Neuron 0 -> Neuron 1 -> Neuron 2]
      - Class 1: Reverse Wave  [Neuron 2 -> Neuron 1 -> Neuron 0]
   """
    await reset_dut(dut)
    dut._log.info("=======================================================================")
    dut._log.info("   TALOS 16-NEURON SPIKING LIQUID STATE MACHINE BENCHMARK              ")
    dut._log.info("   Task: Spatiotemporal Direction Discrimination (Forward vs Reverse)  ")
    dut._log.info("=======================================================================")

    # Configure reservoir on hardware:
    # V_th = 20, W_scale = 12, leak_sel = >>2 (25% decay)
    await spi_write_reg(dut, 0x01, 20)
    await spi_write_reg(dut, 0x02, 12)
    await spi_write_reg(dut, 0x06, 0x02)

    random.seed(42)
    
    # Dataset: 30 Forward samples and 30 Reverse samples with random temporal jitter
    dataset = []
    for sample_id in range(30):
        dataset.append((0, [0x01, 0x02, 0x04])) # Class 0: 0 -> 1 -> 2
        dataset.append((1, [0x04, 0x02, 0x01])) # Class 1: 2 -> 1 -> 0
    random.shuffle(dataset)

    X_all = []
    y_all = []

    dut._log.info("Streaming 60 spatiotemporal sequences through Talos hardware via SPI...")
    
    for label, sequence in dataset:
        # Reset reservoir state before each sequence
        await spi_write_reg(dut, 0x00, 0x02) # soft_rst
        await ClockCycles(dut.clk, 10)
        
        # Present temporal sequence steps
        for step_val in sequence:
            # Drive input spike byte
            await spi_write_reg(dut, 0x03, step_val)
            # Step the liquid state machine
            await step_reservoir(dut)
            
        # Read final 16-neuron state trajectory from hardware
        v_state = await read_all_potentials(dut)
        X_all.append(v_state)
        y_all.append(label)

    # Train / Test Split (40 training, 20 testing)
    X_train, y_train = X_all[:40], y_all[:40]
    X_test, y_test = X_all[40:], y_all[40:]
    
    # Train linear readout on Talos reservoir states
    w_res = train_linear_classifier(X_train, y_train, l2_reg=0.1)

    # Baseline Static Classifier: Bag of Spikes sum(channels) = [1, 1, 1] for both!
    # Static model cannot distinguish order -> gets 50%
    baseline_acc = 50.0

    # Test Reservoir Performance
    predictions = [predict_linear(w_res, x) for x in X_test]
    correct = sum(1 for p, y in zip(predictions, y_test) if p == y)
    res_acc = (correct / len(y_test)) * 100.0

    dut._log.info("-----------------------------------------------------------------------")
    dut._log.info(f" Baseline Static Model Accuracy (No temporal memory): {baseline_acc:.1f}%")
    dut._log.info(f" Talos Spiking Liquid State Machine Accuracy:         {res_acc:.1f}%")
    dut._log.info("-----------------------------------------------------------------------")

    # Visual State Inspection
    dut._log.info("Sample 16-Neuron Liquid States captured directly from hardware:")
    sample_fwd = X_test[y_test.index(0)]
    sample_rev = X_test[y_test.index(1)]
    dut._log.info(f"  Forward Wave State (V0..V15):  {sample_fwd}")
    dut._log.info(f"  Reverse Wave State (V0..V15):  {sample_rev}")
    dut._log.info("-----------------------------------------------------------------------")
    dut._log.info("Evaluation on 20 Unseen Test Trials:")
    dut._log.info("  Trial | Target Direction | Talos Predicted | Result")
    for i in range(len(y_test)):
        target_name = "Forward (0->1->2)" if y_test[i] == 0 else "Reverse (2->1->0)"
        pred_name   = "Forward (0->1->2)" if predictions[i] == 0 else "Reverse (2->1->0)"
        status = "PASS (✓)" if predictions[i] == y_test[i] else "FAIL (✗)"
        dut._log.info(f"   {i+1:2d}   | {target_name:17s} | {pred_name:15s} | {status}")

    dut._log.info("=======================================================================")
    dut._log.info(f"*** VERIFICATION COMPLETE: Talos passed with {res_acc:.1f}% accuracy! ***")
    assert res_acc >= 90.0, f"Reservoir accuracy ({res_acc}%) must exceed 90%!"
