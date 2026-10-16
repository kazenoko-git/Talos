/*
 * Copyright (c) 2026 Ivan
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module ternary_pe (
    input  wire        clk,
    input  wire        rst_n,

    input  wire        clear_acc,    // Clears accumulator to 0 or loads bias if load_bias=1
    input  wire        load_bias,    // When clear_acc=1, load initial_bias into accumulator
    input  wire [31:0] initial_bias, // Signed INT32 bias applied once per output channel
    input  wire        en,

    // Operands
    input  wire [1:0]  weight_code,  // 2'b00: 0, 2'b01: +1, 2'b10: -1, 2'b11: invalid
    input  wire [7:0]  data_in,

    output reg  [31:0] acc,
    output reg         err_invalid,
    output reg         err_overflow
);

    // Sign-extend input to 9 bits signed so negation of -128 yields +128 without overflow.
    wire signed [8:0] data_ext = {{1{data_in[7]}}, data_in};

    // Decode weight and determine effective signed term
    reg signed [8:0] term;
    reg              term_valid;

    always @(*) begin
        case (weight_code)
            2'b00: begin
                term       = 9'sd0;
                term_valid = 1'b1;
            end
            2'b01: begin
                term       = data_ext;
                term_valid = 1'b1;
            end
            2'b10: begin
                // -(-128) becomes -(-9'sd128) = +9'sd128
                term       = -data_ext;
                term_valid = 1'b1;
            end
            default: begin // 2'b11
                term       = 9'sd0;
                term_valid = 1'b0;
            end
        endcase
    end

    // Accumulate with signed overflow detection
    wire signed [31:0] term_ext32 = {{23{term[8]}}, term};
    wire signed [31:0] next_acc   = acc + term_ext32;

    // Signed overflow occurs when two numbers of same sign yield result of opposite sign.
    wire overflow_detected = (acc[31] == term_ext32[31]) && (next_acc[31] != acc[31]);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            acc          <= 32'sd0;
            err_invalid  <= 1'b0;
            err_overflow <= 1'b0;
        end else if (clear_acc) begin
            acc          <= load_bias ? initial_bias : 32'sd0;
            err_invalid  <= 1'b0;
            err_overflow <= 1'b0;
        end else if (en) begin
            if (!term_valid) begin
                err_invalid <= 1'b1;
            end
            if (overflow_detected) begin
                err_overflow <= 1'b1;
            end
            acc <= next_acc;
        end
    end

endmodule
