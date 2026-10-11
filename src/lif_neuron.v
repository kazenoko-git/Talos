`default_nettype none

// Leaky Integrate-and-Fire (LIF) Neuron Cell.
// This should -  in theory - implement discrete-time leaky integration, threshold comparison, and spike reset.

module lif_neuron (
    input  wire              clk,
    input  wire              rst_n,
    input  wire              step_tick,     // 1 cycle pulse to enable temporal integration
    input  wire signed [7:0] i_syn,         // Total accumulated synaptic current for a step
    input  wire signed [7:0] v_th,          // Firing threshold
    input  wire        [1:0] leak_sel,      // Leak shift: 0 is none, 1=>>3 (12.5%), 2=>>2 (25%), 3=>>1 (50%)
    output reg               spike_out,     // 1 cycle spike output pulse
    output reg  signed [7:0] v_mem          // Current membrane potential
);

    // Compute arithmetic right shift for leakage
    wire signed [7:0] leak_val;
    assign leak_val = (leak_sel == 2'b01) ? (v_mem >>> 3) :
                      (leak_sel == 2'b10) ? (v_mem >>> 2) :
                      (leak_sel == 2'b11) ? (v_mem >>> 1) : 8'sd0;

    // Next potential calculation with saturation limits
    reg signed [8:0] v_next_raw;
    reg signed [7:0] v_next_clamped;

    always @(*) begin
        // Subtract leak, add synaptic input current
        v_next_raw = v_mem - leak_val + i_syn;

        // Saturate to 8-bit signed limits [-128, +127] to prevent wrap-around
        if (v_next_raw > 9'sd127)
            v_next_clamped = 8'sd127;
        else if (v_next_raw < -9'sd128)
            v_next_clamped = -8'sd128;
        else
            v_next_clamped = v_next_raw[7:0];
    end

    // Sequential state update
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            v_mem     <= 8'sd0;
            spike_out <= 1'b0;
        end else if (step_tick) begin
            if (v_next_clamped >= v_th) begin
                spike_out <= 1'b1;     // Neuron fires
                v_mem     <= 8'sd0;    // Reset potential to baseline
            end else begin
                spike_out <= 1'b0;
                v_mem     <= v_next_clamped;
            end
        end 
        // when step_tick low, hold spike_out and v_mem until next step_tick
    end

endmodule
