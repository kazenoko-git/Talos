/*
    * Copyright (c) 2026 Ivan
    * SPDX-License-Identifier: Apache-2.0
*/

`default_nettype none
`timescale 1ns/1ps

module tb_partial_sum_bank (
    input wire clk,
    input wire rst_n,
    input wire wr_en,
    input wire [1:0] wr_sel,
    input wire signed [31:0] wr_data,
    input wire clear_all,
    input wire [1:0] rd_sel,
    output wire signed [31:0] rd_data,
    output wire signed [31:0] sum0,
    output wire signed [31:0] sum1,
    output wire signed [31:0] sum2,
    output wire signed [31:0] sum3
);

    initial begin
        $dumpfile("tb_partial_sum_bank.fst");
        $dumpvars(0, tb_partial_sum_bank);
        #1;
    end

    partial_sum_bank dut (
	.clk      (clk),
	.rst_n    (rst_n),
	.wr_en    (wr_en),
	.wr_sel   (wr_sel),
	.wr_data  (wr_data),
	.clear_all(clear_all),
	.rd_sel   (rd_sel),
	.rd_data  (rd_data),
	.sum0     (sum0),
	.sum1     (sum1),
	.sum2     (sum2),
	.sum3     (sum3)
    );

endmodule
