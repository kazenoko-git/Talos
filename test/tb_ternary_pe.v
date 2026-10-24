/*
 * Copyright (c) 2026 Ivan
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none
`timescale 1ns / 1ps

/* Testbench wrapper for ternary_pe module */
module tb_ternary_pe (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        clear_acc,
    input  wire        load_bias,
    input  wire [31:0] initial_bias,
    input  wire        en,
    input  wire [1:0]  weight_code,
    input  wire [7:0]  data_in,
    output wire [31:0] acc,
    output wire        err_invalid,
    output wire        err_overflow
);

    // Dump waveform for inspection
    initial begin
        $dumpfile("tb_ternary_pe.fst");
        $dumpvars(0, tb_ternary_pe);
        #1;
    end

    ternary_pe dut (
        .clk(clk),
        .rst_n(rst_n),
        .clear_acc(clear_acc),
        .load_bias(load_bias),
        .initial_bias(initial_bias),
        .en(en),
        .weight_code(weight_code),
        .data_in(data_in),
        .acc(acc),
        .err_invalid(err_invalid),
        .err_overflow(err_overflow)
    );

endmodule
