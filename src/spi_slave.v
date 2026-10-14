/*
* Copyright (c) 2026 Ivan
* SPDX-License-Identifier: Apache-2.0
*/

`default_nettype none

module spi_slave (
    input wire clk,    
    input wire rst_n, 
    input wire sclk,   // ui_in[0]
    input wire cs_n,   // ui_in[2]
    input wire mosi,   // ui_in[1]
    output wire miso,  // ui_out[0]

    output reg [7:0] rx_byte, // Byte receive 
    output reg rx_valid,      // Pulse when rx_byte ready
    input wire [7:0] tx_byte, // Byte transmission to MC
    input wire tx_load,       // Pulse load tx_byte into shift register
    output wire cs_active     // Should be high when cs_n held low
);
    
    // 2-stage flip-flop sync to prevent metastability
    reg [2:0] sclk_sync;
    reg [1:0] cs_n_sync;
    reg [1:0] mosi_sync;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sclk_sync <= 3'b000;
            cs_n_sync <= 2'b11;
            mosi_sync <= 2'b00;
        end else begin
            sclk_sync <= {sclk_sync[1:0], sclk};
            cs_n_sync <= {cs_n_sync[0], cs_n};
            mosi_sync <= {mosi_sync[0], mosi};
        end
    end

    // edge detectors
    wire sclk_rising = (sclk_sync[2:1] == 2'b01);
    wire sclk_falling = (sclk_sync[2:1] == 2'b10);
    assign cs_active = ~cs_n_sync[1];

    // bit reception counter and shift register
    reg [2:0] bit_cnt;
    /* verilator lint_off UNUSEDSIGNAL */
    reg [7:0] rx_shreg;
    /* verilator lint_on UNUSEDSIGNAL */

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            bit_cnt <= 3'd0;
            rx_shreg <= 8'd0;
            rx_byte <= 8'd0;
            rx_valid <= 1'b0;
        end else if (!cs_active) begin
            bit_cnt <= 3'd0;
            rx_valid <= 1'b0;
        end else begin
            rx_valid <= 1'b0;
            if(sclk_rising) begin
                rx_shreg <= {rx_shreg[6:0], mosi_sync[1]};
                bit_cnt <= bit_cnt + 3'd1;
                if (bit_cnt == 3'd7) begin
                    rx_byte <= {rx_shreg[6:0], mosi_sync[1]};
                    rx_valid <= 1'b1;
                end
            end
        end
    end

    // outgoing MISO shift register (SPI Mode 0)
    reg [7:0] tx_shreg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tx_shreg <= 8'd0;
        end else if (tx_load) begin
            tx_shreg <= tx_byte;
        end else if (cs_active && sclk_falling && (bit_cnt != 3'd0)) begin
            tx_shreg <= {tx_shreg[6:0], 1'b0}; // shift out the next bit only after master samples current bit
        end
    end

    assign miso = cs_active ? tx_shreg[7] : 1'b0;

endmodule
        