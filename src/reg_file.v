/*
 * Copyright (c) 2026 Ivan
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module reg_file (
    input  wire        clk,           // Clock (16 MHz)
    input  wire        rst_n,         // Active low reset

    // spi_slave interface
    input  wire [7:0]  rx_byte,       // Received byte from SPI
    input  wire        rx_valid,      // Pulse when rx_byte ready
    input  wire        cs_active,     // Active while CS_n low
    output reg  [7:0]  tx_byte,       // Outgoing byte to SPI MISO
    output reg         tx_load,       // Pulse to load tx_byte into SPI shift register

    // dot_product_engine interface
    input  wire [23:0] acc_out,       // 24 bit accumulator value
    input  wire [7:0]  act_out,       // 8 bit post-activation value
    input  wire        overflow,      
    input  wire        busy,          

    output reg         start_compute, // 1 cycle compute trigger
    output reg         rst_acc,       // 1 cycle accumulator reset pulse
    output reg  [1:0]  mode,          // Precision mode (00=BitNet, 01=BNN)
    output reg         act_en,        // Fused activation enable
    output reg  [63:0] weights,       // 32 packed weights (2 bits each)
    output reg  [255:0] activations,  // 32 packed activations (8 bits each)
    output reg         irq            // Interrupt pulse on completion
);

  localparam STATE_IDLE = 2'd0;
  localparam STATE_ADDR = 2'd1;
  localparam STATE_DATA = 2'd2;

  reg [1:0] state;
  reg       is_read;
  reg [6:0] current_addr;
  reg [5:0] stream_cnt; // Counts 0 to 63 bytes during stream

  // Read multiplexer helper function
  function [7:0] get_reg_data(input [6:0] addr);
    case (addr)
      7'h00:   get_reg_data = {4'b0, act_en, mode, 1'b0};
      7'h01:   get_reg_data = {6'b0, overflow, busy};
      7'h02:   get_reg_data = acc_out[7:0];
      7'h03:   get_reg_data = acc_out[15:8];
      7'h04:   get_reg_data = acc_out[23:16];
      7'h05:   get_reg_data = act_out;
      default: get_reg_data = 8'h00;
    endcase
  endfunction

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state         <= STATE_IDLE;
      is_read       <= 1'b0;
      current_addr  <= 7'd0;
      stream_cnt    <= 6'd0;
      tx_byte       <= 8'd0;
      tx_load       <= 1'b0;
      start_compute <= 1'b0;
      rst_acc       <= 1'b0;
      mode          <= 2'b00;
      act_en        <= 1'b0;
      weights       <= 64'd0;
      activations   <= 256'd0;
      irq           <= 1'b0;
    end else if (!cs_active) begin
      // Reset state machine whenever CS_n is deselected
      state         <= STATE_IDLE;
      stream_cnt    <= 6'd0;
      tx_load       <= 1'b0;
      start_compute <= 1'b0;
      rst_acc       <= 1'b0;
      irq           <= 1'b0;
    end else begin
      // Default single-cycle strobes
      tx_load       <= 1'b0;
      start_compute <= 1'b0;
      rst_acc       <= 1'b0;
      irq           <= 1'b0;

      case (state)
        STATE_IDLE: begin
          if (rx_valid) begin
            // First byte should always be [7]=R/W, [6:0]=Address
            is_read      <= rx_byte[7];
            current_addr <= rx_byte[6:0];
            state        <= STATE_DATA;

            if (rx_byte[7]) begin
              // preload first response byte onto MISO
              tx_byte <= get_reg_data(rx_byte[6:0]);
              tx_load <= 1'b1;
            end
          end
        end

        STATE_DATA: begin
          if (rx_valid) begin
            if (is_read) begin
              // auto-increment address for sequential accumulator reads
              current_addr <= current_addr + 7'd1;
              tx_byte      <= get_reg_data(current_addr + 7'd1);
              tx_load      <= 1'b1;
            end else begin
              // Write command
              if (current_addr == 7'h10) begin
                // Stream Port (0x10): 64 bytes burst
                if (stream_cnt < 6'd32) begin
                  activations[stream_cnt * 8 +: 8] <= rx_byte;
                end else begin
                  weights[(stream_cnt - 6'd32) * 2 +: 2] <= rx_byte[1:0];
                end

                stream_cnt <= stream_cnt + 6'd1;

                if (stream_cnt == 6'd63) begin
                  // 64th byte received -> trigger hardware compute
                  start_compute <= 1'b1;
                  irq           <= 1'b1;
                  stream_cnt    <= 6'd0;
                end
              end else if (current_addr == 7'h00) begin
                // Control register write
                rst_acc <= rx_byte[0];
                mode    <= rx_byte[2:1];
                act_en  <= rx_byte[3];
              end
            end
          end
        end

        default: state <= STATE_IDLE;
      endcase
    end
  end

endmodule
