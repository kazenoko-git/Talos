/*
    * Copyright (c) 2026 Ivan
    * SPDX-License-Identifier: Apache-2.0
*/

`default_nettype none

module output_scaler (
    input wire clk,
    input wire rst_n,

    // control handshakes

    input wire start,
    input wire raw_mode, // when 1, bypass scaling and output raw acc
    input wire relu,     // when 1, apply ReLU before saturation

    // operands
    input wire signed [31:0] acc,
    input wire [15:0] multiplier, // unsigned 16 bit multiplier
    input wire [4:0] shift,

    output reg done,
    output reg [7:0] data_out_int8,
    output reg signed [31:0] data_out_raw,
    output reg busy
);

    // signed 48 bit product (acc * multiplier)

    reg s1_valid;
    reg s1_raw_mode;
    reg s1_relu;
    reg signed [31:0] s1_acc;
    reg [15:0] s1_multiplier;
    reg [4:0] s1_shift;
    reg signed [47:0] s1_prod;

    // zero extend unsigned multiplier by 1 bit to multiply as positive signed operand

    wire signed [47:0] mult_result = acc * $signed({1'b0, multiplier});

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s1_valid <= 1'b0;
            s1_raw_mode <= 1'b0;
            s1_relu <= 1'b0;
            s1_acc <= 32'sd0;
            s1_multiplier <= 16'b0;
            s1_shift <= 5'b0;
            s1_prod <= 48'sd0;
            busy <= 1'b0;
        end else if (start) begin
            s1_valid <= 1'b1;
            s1_raw_mode <= raw_mode;
            s1_relu <= relu;
            s1_acc <= acc;
            s1_multiplier <= multiplier;
            s1_shift <= shift;
            s1_prod <= mult_result;
            busy <= 1'b1;
        end else begin
            s1_valid <= 1'b0;
        end
    end

    // This is the next stage.
    // Symetrical rounding, Shift, ReLU and Saturation

    // Half divisor: 1 << (shift - 1) when shift > 0
    wire signed [47:0] half = (s1_shift > 5'd0) ? (48'sd1) <<< (s1_shift - 5'd1) : 48'sd0;

    // Absolute value of product for symmetric round-away-from-zero

    wire signed [47:0] s1_prod_abs = (s1_prod >= 48'sd0) ? s1_prod : -s1_prod;
    wire signed [47:0] shifted_abs = (s1_prod_abs + half) >>> s1_shift;

    reg signed [47:0] rounded_val;
    always @(*) begin
        if (s1_multiplier == 16'd0) begin
            rounded_val = 48'sd0;
        end else if (s1_shift == 5'd0) begin
            rounded_val = s1_prod;
        end else if (s1_prod >= 48'sd0) begin
            rounded_val = shifted_abs;
        end else begin
            rounded_val = -shifted_abs;
        end
    end

    // apply the optional ReLU

    wire signed [47:0] relu_val = (s1_relu && (rounded_val < 48'sd0)) ? 48'sd0 : rounded_val;

    // Saturation clamp to signed INT8

    reg signed [7:0] sat_int8;
    always @(*) begin
        if (relu_val > 48'sd127) begin
            sat_int8 = 8'sd127;
        end else if (relu_val < -48'sd128) begin
            sat_int8 = -8'sd128;
        end else begin
            sat_int8 = relu_val[7:0];
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            done <= 1'b0;
            data_out_int8 <= 8'sd0;
            data_out_raw <= 32'sd0;
        end else if (s1_valid) begin
            done <= 1'b1;
            busy <= 1'b0;
            data_out_raw <= s1_acc;
            data_out_int8 <= sat_int8;
        end else begin
            done <= 1'b0;
        end
    end

endmodule
