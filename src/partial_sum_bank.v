/*
 * Copyright (c) 2026 Ivan
 * SPDX-License-Identifier: Apache-2.0
*/

`default_nettype none

module partial_sum_bank(
    input wire clk,
    input wire rst_n,

    // write / load port
    input wire wr_en,
    input wire [1:0] wr_sel,
    input wire signed [31:0] wr_data,

    // sync clear
    input wire clear_all,

    // read port
    input wire [1:0] rd_sel,
    output reg signed [31:0] rd_data,

    // direct parallel outputs for inspection / wide tap
    output wire signed [31:0] sum0,
    output wire signed [31:0] sum1,
    output wire signed [31:0] sum2,
    output wire signed [31:0] sum3
);

    reg signed [31:0] bank0;
    reg signed [31:0] bank1;
    reg signed [31:0] bank2;
    reg signed [31:0] bank3;

    assign sum0 = bank0;
    assign sum1 = bank1;
    assign sum2 = bank2;
    assign sum3 = bank3;

    // explicit mux to avoid Verilog-2001 array sensitivity warnings
    always @(*) begin
        case (rd_sel)
            2'd0: rd_data = bank0;
            2'd1: rd_data = bank1;
            2'd2: rd_data = bank2;
            2'd3: rd_data = bank3;
            default: rd_data = 32'sd0;
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            bank0 <= 32'sd0;
            bank1 <= 32'sd0;
            bank2 <= 32'sd0;
            bank3 <= 32'sd0;
        end else if (clear_all) begin
            bank0 <= 32'sd0;
            bank1 <= 32'sd0;
            bank2 <= 32'sd0;
            bank3 <= 32'sd0;
        end else if (wr_en) begin
            case (wr_sel)
                2'd0: bank0 <= wr_data;
                2'd1: bank1 <= wr_data;
                2'd2: bank2 <= wr_data;
                2'd3: bank3 <= wr_data;
            endcase
        end
    end
endmodule
