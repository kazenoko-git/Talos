`default_nettype none

// 16 Neuron Spiking Recurrent Reservoir (or a Liquid State Machine)
// Implements fixed sparse ternary recurrent connectivity (don't know what the fuck that means)
// i.e excitatory, inhibitory, and silent.

module spiking_reservoir (
    input  wire              clk,
    input  wire              rst_n,
    input  wire              step_tick,       // 1 cycle time step pulse
    input  wire        [7:0] ext_spike_in,    // 8 external spike events from SPI/input
    input  wire signed [7:0] v_th,            // firing threshold
    input  wire        [1:0] leak_sel,        // leak shift: 0=none, 1=>>3, 2=>>2, 3=>>1
    input  wire signed [7:0] weight_scale,    // synaptic weight magnitude
    output wire       [15:0] spikes_out,      // 16-bit reservoir spike output state
    output wire      [127:0] v_mem_all        // all 16 membrane potentials packed for SPI inspection (16 * 8 bits)
);

    genvar i;
    generate
        for (i = 0; i < 16; i = i + 1) begin : gen_neurons
            // Static connection indices for recurrent topology
            localparam integer PRE_EXC   = (i + 15) % 16; // Neighbor i-1
            localparam integer PRE_INH   = (i + 1)  % 16; // Neighbor i+1
            localparam integer PRE_CROSS = (i + 5)  % 16; // Long-range cross connection

            // Compute total synaptic input for this neuron
            reg signed [9:0] i_syn_sum;
            reg signed [7:0] i_syn_clamped;

            always @(*) begin
                i_syn_sum = 10'sd0;

                // External spike input (neurons 0-7)
                if (i < 8) begin
                    if (ext_spike_in[i])
                        i_syn_sum = i_syn_sum + (weight_scale <<< 1); // 2x weight for external input
                end

                // Local excitatory recurrence from neighbor (i-1)
                if (spikes_out[PRE_EXC])
                    i_syn_sum = i_syn_sum + weight_scale;

                // Local inhibitory recurrence from neighbor (i+1)
                if (spikes_out[PRE_INH])
                    i_syn_sum = i_syn_sum - weight_scale;

                // Long-range cross recurrence from (i+5)
                if (spikes_out[PRE_CROSS]) begin
                    if (i[0] == 1'b0)
                        i_syn_sum = i_syn_sum + weight_scale; // Even neurons: excitatory cross
                    else
                        i_syn_sum = i_syn_sum - weight_scale; // Odd neurons: inhibitory cross
                end

                // Saturate to 8-bit signed limits [-128, +127]
                if (i_syn_sum > 10'sd127)
                    i_syn_clamped = 8'sd127;
                else if (i_syn_sum < -10'sd128)
                    i_syn_clamped = -8'sd128;
                else
                    i_syn_clamped = i_syn_sum[7:0];
            end

            // Instantiate LIF neuron cell
            wire signed [7:0] v_mem_i;
            lif_neuron u_neuron (
                .clk       (clk),
                .rst_n     (rst_n),
                .step_tick (step_tick),
                .i_syn     (i_syn_clamped),
                .v_th      (v_th),
                .leak_sel  (leak_sel),
                .spike_out (spikes_out[i]),
                .v_mem     (v_mem_i)
            );

            // Pack membrane potential into output bus
            assign v_mem_all[i*8 +: 8] = v_mem_i;
        end
    endgenerate

endmodule