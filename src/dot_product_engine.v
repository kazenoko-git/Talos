/*
 * Copyright (c) 2026 Ivan
 * SPDX-License-Identifier: Apache-2.0
*/

`default_nettype none 

module dot_product_engine (
    input wire clk,            // clock (16MHz)
    input wire rst_n,          // active low sys reset
    input wire start_compute,  // 1 cycle strobe to calculate and accum
    input wire rst_acc,        // 1 cycle strobe to reset accum to 0
    input wire [1:0] mode,     // 00 = BitNet b1.58 Ternary, 01 = 1 bit BNN
    input wire act_en,         // 1 = Enable fused ReLU
    input wire [63:0] weights, // 32 packed weights (2 bits each)
    input wire [255:0] activations, // 32 packed activations (8 signed bits)
    output reg [23:0] acc_out, // 24 bit saturation
    output wire [7:0] act_out, // 8 bit fused activation
    output reg overflow,       // sticky overflow flag
    output reg busy            // high when compute active
);

    // Step 1: 32 Parallel Lanes (without Multiplier)

    wire signed [8:0] lane_prod [0:31];

    genvar i;
    generate
        for (i = 0; i < 32; i = i + 1) begin : gen_lanes
            wire signed [7:0] act_i = activations[i*8 +: 8];
            wire [1:0] w_i = weights[i*2 +: 2];
            
            // BitNet ternary mode: 00=0, 01=+1, 11=-1
            // BNN mode: bit 0 of act XNOR bit 0 of weight -> +1 or -1

            wire signed [8:0] ternary_prod = {w_i == 2'b01} ? {act_i[7], act_i} :
                {w_i == 2'b11} ? - {act_i[7], act_i} : 9'b0;

            wire signed [8:0] bnn_prod = (act_i[0] ~^ w_i[0]) ? 9'sd1 : -9'sd1;

            assign lane_prod[i] = (mode == 2'b01) ? bnn_prod : ternary_prod;
        end
    endgenerate

    // Step 2: 5 Level Adder Tree (32->16->8->4->2->1)
    wire signed [9:0]  tree_l1 [0:15];
    wire signed [10:0] tree_l2 [0:7];
    wire signed [11:0] tree_l3 [0:3];
    wire signed [12:0] tree_l4 [0:1];
    wire signed [13:0] chunk_sum;

    // Level 1: 32 inputs -> 16 sums (10-bit signed)
    for (i = 0; i < 16; i = i + 1) begin : gen_l1
    assign tree_l1[i] = lane_prod[2*i] + lane_prod[2*i + 1];
    end

    // Level 2: 16 inputs -> 8 sums (11-bit signed)
    for (i = 0; i < 8; i = i + 1) begin : gen_l2
    assign tree_l2[i] = tree_l1[2*i] + tree_l1[2*i + 1];
    end

    // Level 3: 8 inputs -> 4 sums (12-bit signed)
    for (i = 0; i < 4; i = i + 1) begin : gen_l3
    assign tree_l3[i] = tree_l2[2*i] + tree_l2[2*i + 1];
    end

    // Level 4: 4 inputs -> 2 sums (13-bit signed)
    for (i = 0; i < 2; i = i + 1) begin : gen_l4
    assign tree_l4[i] = tree_l3[2*i] + tree_l3[2*i + 1];
    end

    // Level 5: 2 inputs -> 1 final chunk sum (14-bit signed)
    assign chunk_sum = tree_l4[0] + tree_l4[1];

    // Step 3: Saturation Accumulator (24 bit)

    // 25 bit temp sum detects overflow beyond 24 bit limits
    wire signed [24:0] ext_acc       = {acc_out[23], acc_out};
    wire signed [24:0] ext_chunk_sum = {{11{chunk_sum[13]}}, chunk_sum};
    wire signed [24:0] next_sum      = ext_acc + ext_chunk_sum;
    localparam signed [24:0] POS_SAT = 25'sh07FFFFF; // +8,388,607
    localparam signed [24:0] NEG_SAT = -25'sh0800000; // -8,388,608
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
        acc_out  <= 24'sd0;
        overflow <= 1'b0;
        busy     <= 1'b0;
        end else if (rst_acc) begin
        acc_out  <= 24'sd0;
        overflow <= 1'b0;
        busy     <= 1'b0;
        end else if (start_compute) begin
        busy <= 1'b0;
        if (next_sum > POS_SAT) begin
            acc_out  <= 24'h7FFFFF;
            overflow <= 1'b1;
        end else if (next_sum < NEG_SAT) begin
            acc_out  <= 24'h800000;
            overflow <= 1'b1;
        end else begin
            acc_out <= next_sum[23:0];
        end
        end
    end

    // Step 4: Fused Activation (ReLU / Clamp to 8 bit signed)

    wire signed [23:0] relu_val = (acc_out[23]) ? 24'sd0 : acc_out;
    wire signed [23:0] act_src  = act_en ? relu_val : acc_out;
    // Clamp to [-128, +127]
    assign act_out = (act_src > 24'sd127)  ? 8'sd127  : (act_src < -24'sd128) ? -8'sd128 : act_src[7:0];
endmodule