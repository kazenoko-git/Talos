/*
 * Copyright (c) 2026 Ivan
 * SPDX-License-Identifier: Apache-2.0
*/

`default_nettype none

module input_buffer #(
    parameter BUFFER_SIZE = 64,
    parameter ADDR_WIDTH = 6
) (
    input wire clk,
    input wire rst_n,

    // write from memory controller or host SPI

    input wire wr_en,
    input wire [ADDR_WIDTH-1:0] wr_addr,
    input wire [7:0] wr_data,

    // read to PE ALU or Host SPI

    input wire [ADDR_WIDTH-1:0] rd_addr,
    output wire [7:0] rd_data
);

    reg [7:0] mem [0:BUFFER_SIZE-1];

    // Combinational read port for single cycle ALU operand deliver

    assign rd_data = (rd_addr < BUFFER_SIZE) ? mem[rd_addr] : 8'h00;

    integer i;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (i = 0; i < BUFFER_SIZE; i = i + 1) begin
                mem[i] <= 8'h00;
            end
        end else if (wr_en && (wr_addr < BUFFER_SIZE)) begin
            mem[wr_addr] <= wr_data;
        end
    end
endmodule
