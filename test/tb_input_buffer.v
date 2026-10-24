/*
    * Copyright (c) 2026 Ivan
    * SPDX-License-Identifier: Apache-2.0
*/

`default_nettype none
`timescale 1ns/1ps

module tb_input_buffer (
    input wire clk,
    input wire rst_n,
    input wire wr_en,
    input wire [5:0] wr_addr,
    input wire [7:0] wr_data,
    input wire [5:0] rd_addr,
    output wire [7:0] rd_data
);

    initial begin
        $dumpfile("tb_input_buffer.fst");
        $dumpvars(0, tb_input_buffer);
        #1;
    end

    input_buffer #(
        .BUFFER_SIZE(64),
        .ADDR_WIDTH(6)
    ) uut (
        .clk(clk),
        .rst_n(rst_n),
        .wr_en(wr_en),
        .wr_addr(wr_addr),
        .wr_data(wr_data),
        .rd_addr(rd_addr),
        .rd_data(rd_data)
    );
endmodule
