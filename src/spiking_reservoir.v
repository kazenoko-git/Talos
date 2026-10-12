/*
* Copyright (c) 2026 Ivan
* SPDX-License-Identifier: Apache-2.0
*/

`default_nettype none

// 16-Neuron Time Multiplexed Spiking Recurrent Reservoir (Liquid State Machine) [corpo jargon ass shit]
// UPDATE: Now sequences through 16 neurons across 16 clock cycles using a single shared LIF ALU, as it was taking up too much tile space before.
// TODO: possible further drawbacks needed to be tested with serial architecture.
// Features ternary recurrent synapses {-1, 0, +1} * weight_scale and double-buffered spikes.

module spiking_reservoir (
    input wire clk,
    input wire rst_n,
    input wire step_tick,       // 1 cycle time step trigger pulse
    input wire [7:0] ext_spike_in,    // 8 external spike events from SPI/input
    input wire signed [7:0] v_th,            // firing threshold
    input wire [1:0] leak_sel,        // leak shift: 0=none, 1=>>3, 2=>>2, 3=>>1
    input wire signed [7:0] weight_scale,    // synaptic weight magnitude
    input wire [3:0] v_mem_addr,         // inspection address for the register file
    output reg busy,
    output reg [15:0] spikes_out,      // 16-bit reservoir spike output state
    // output wire [127:0] v_mem_all        // all 16 membrane potentials packed (16 * 8 bits)
    output wire signed [7:0] v_mem_data     // membrane potential for inspected neuron
);

    // 16 x 8-bit membrane potential register bank
    reg signed [7:0] v_mem [0:15];

    assign v_mem_data = v_mem[v_mem_addr];

    reg [15:0] spikes_latched;   // step t-1 spikes held static as recurrent inputs
    reg [7:0] ext_spike_latched; // external spike snapshot for current step
    /* verilator lint_off UNUSEDSIGNAL */
    reg [15:0] spikes_next;      // step t spikes accum across 16 cycles
    /* verilator lint_on UNUSEDSIGNAL */

    // Sequencer state
    reg [3:0] neuron_idx;

    // Recurrent neighbor connection indices 
    wire [3:0] pre_exc = neuron_idx - 4'd1; // Neighbor i-1
    wire [3:0] pre_inh = neuron_idx + 4'd1; // Neighbor i+1
    wire [3:0] pre_cross = neuron_idx + 4'd5; // Cross neighbor i+5

    // Sign-extended 10-bit weight scale to prevent Verilator WIDTHEXPAND warnings
    wire signed [9:0] w_scale_ext = {{2{weight_scale[7]}}, weight_scale};
    wire signed [9:0] w_scale_2x  = w_scale_ext <<< 1;

    // Synaptic current accumulator for active neuron_idx
    reg signed [9:0] i_syn_sum;
    reg signed [7:0] i_syn_clamped;

    always @(*) begin
        i_syn_sum = 10'sd0;

        // External input drive (neurons 0..7 only, using latched snapshot)
        if (neuron_idx < 4'd8) begin
            if (ext_spike_latched[neuron_idx[2:0]])
                i_syn_sum = i_syn_sum + w_scale_2x;
        end

        // Local excitatory recurrence from neighbor (idx - 1)
        if (spikes_latched[pre_exc])
            i_syn_sum = i_syn_sum + w_scale_ext;

        // Local inhibitory recurrence from neighbor (idx + 1)
        if (spikes_latched[pre_inh])
            i_syn_sum = i_syn_sum - w_scale_ext;

        // Long-range cross recurrence from (idx + 5)
        if (spikes_latched[pre_cross]) begin
            if (neuron_idx[0] == 1'b0)
                i_syn_sum = i_syn_sum + w_scale_ext; // Even neurons: excitatory cross
            else
                i_syn_sum = i_syn_sum - w_scale_ext; // Odd neurons: inhibitory cross
        end

        // Clamp to signed 8 bit limits [-128, +127]
        if (i_syn_sum > 10'sd127)
            i_syn_clamped = 8'sd127;
        else if (i_syn_sum < -10'sd128)
            i_syn_clamped = -8'sd128;
        else
            i_syn_clamped = i_syn_sum[7:0];
    end

    // Single shared LIF ALU instance 
    wire signed [7:0] alu_v_mem_in = v_mem[neuron_idx];
    wire              alu_spike_out;
    wire signed [7:0] alu_v_mem_out;

    lif_neuron u_lif_alu (
        .v_mem_in (alu_v_mem_in),
        .i_syn (i_syn_clamped),
        .v_th (v_th),
        .leak_sel  (leak_sel),
        .spike_out (alu_spike_out),
        .v_mem_out (alu_v_mem_out)
    );

    // 16-cycle step sequencing logic
    integer k;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy           <= 1'b0;
            neuron_idx     <= 4'd0;
            spikes_latched <= 16'd0;
            ext_spike_latched <= 8'd0;
            spikes_next    <= 16'd0;
            spikes_out     <= 16'd0;
            for (k = 0; k < 16; k = k + 1) begin
                v_mem[k] <= 8'sd0;
            end
        end else begin
            if (step_tick && !busy) begin
                busy           <= 1'b1;
                neuron_idx     <= 4'd0;
                spikes_latched <= spikes_out; // freeze previous step spikes as inputs
                ext_spike_latched <= ext_spike_in;
                spikes_next    <= 16'd0;
            end else if (busy) begin
                // Update potential and record spike for active neuron
                v_mem[neuron_idx]       <= alu_v_mem_out;
                spikes_next[neuron_idx] <= alu_spike_out;

                if (neuron_idx == 4'd15) begin
                    busy       <= 1'b0;
                    spikes_out <= {alu_spike_out, spikes_next[14:0]};
                end else begin
                    neuron_idx <= neuron_idx + 4'd1;
                end
            end
        end
    end

    // consume bit 15 to suppress the unused bit warning

    wire _unused = &{spikes_next[15], 1'b0};

endmodule