/*
 * Copyright (c) 2026 Ivan
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none
`timescale 1ns / 1ps

/* Testbench wrapper for output_scaler module */
module tb_output_scaler (
    input  wire               clk,
    input  wire               rst_n,
    input  wire               start,
    input  wire               raw_mode,
    input  wire               relu,
    input  wire signed [31:0] acc,
    input  wire        [15:0] multiplier,
    input  wire        [4:0]  shift,
    output wire               done,
    output wire        [7:0]  data_out_int8,
    output wire signed [31:0] data_out_raw,
    output wire               busy
);

    // Dump waveform for inspection
    initial begin
        $dumpfile("tb_output_scaler.fst");
        $dumpvars(0, tb_output_scaler);
        #1;
    end

    output_scaler dut (
        .clk(clk),
        .rst_n(rst_n),
        .start(start),
        .raw_mode(raw_mode),
        .relu(relu),
        .acc(acc),
        .multiplier(multiplier),
        .shift(shift),
        .done(done),
        .data_out_int8(data_out_int8),
        .data_out_raw(data_out_raw),
        .busy(busy)
    );

endmodule
