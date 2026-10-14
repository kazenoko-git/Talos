/*
* Copyright (c) 2026 Ivan
* SPDX-License-Identifier: Apache-2.0
*/

`default_nettype none

// Leaky Integrate-and-Fire (LIF) Neuron Arithmetic Engine (UPDATED with non parallel architecture)
// This computes discrete-time leak, synaptic current integration, clamping, and threshold firing.
// Non parallel architecture is probably awful... well it's decent, but it drops true clockspeed to 1MHz. 

module lif_neuron (
    input wire signed [7:0] v_mem_in,      // Current membrane potential
    input wire signed [7:0] i_syn,         // Total accumulated synaptic current
    input wire signed [7:0] v_th,          // Firing threshold
    input wire [1:0] leak_sel,             // Leak shift: 0=none, 1=>>3 (12.5%), 2=>>2 (25%), 3=>>1 (50%)
    output wire spike_out,                 // 1 if neuron crosses threshold
    output wire signed [7:0] v_mem_out     // Next potential (reset to 0 on spike, else clamped potential)
);

    // Arithmetic right shift for leakage decay
    wire signed [7:0] leak_val;
    assign leak_val = (leak_sel == 2'b01) ? (v_mem_in >>> 3) :
                      (leak_sel == 2'b10) ? (v_mem_in >>> 2) :
                      (leak_sel == 2'b11) ? (v_mem_in >>> 1) : 8'sd0;

    // Next potential calculation with saturation limits
    reg signed [8:0] v_next_raw;
    reg signed [7:0] v_next_clamped;

    always @(*) begin
        // Subtract leak, add synaptic input current
        v_next_raw = v_mem_in - leak_val + i_syn;

        // Saturate to 8-bit signed limits [-128, +127] to prevent wrap-around
        if (v_next_raw > 9'sd127)
            v_next_clamped = 8'sd127;
        else if (v_next_raw < -9'sd128)
            v_next_clamped = -8'sd128;
        else
            v_next_clamped = v_next_raw[7:0];
    end

    // Threshold check and reset
    assign spike_out = (v_next_clamped >= v_th);
    assign v_mem_out = spike_out ? 8'sd0 : v_next_clamped;

endmodule

