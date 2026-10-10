/*
 * Copyright (c) 2026 Ivan
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_kazenoko_talos (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // Tile enable
    input  wire       clk,      // Clock (16 MHz)
    input  wire       rst_n     // Active-low asynchronous reset
);

  // Dedicated SPI inputs
  wire sclk = ui_in[0];
  wire mosi = ui_in[1];
  wire cs_n = ui_in[2];

  // Dedicated outputs
  wire miso;
  wire busy;
  wire irq;

  // Internal interconnect wires
  wire [7:0]   rx_byte;
  wire         rx_valid;
  wire         cs_active;
  wire [7:0]   tx_byte;
  wire         tx_load;

  wire [23:0]  acc_out;
  wire [7:0]   act_out;
  wire         overflow;
  wire         start_compute;
  wire         rst_acc;
  wire [1:0]   mode;
  wire         act_en;
  wire [63:0]  weights;
  wire [255:0] activations;

  // SPI Slave instance
  spi_slave u_spi (
      .clk       (clk),
      .rst_n     (rst_n),
      .sclk      (sclk),
      .mosi      (mosi),
      .cs_n      (cs_n),
      .miso      (miso),
      .rx_byte   (rx_byte),
      .rx_valid  (rx_valid),
      .tx_byte   (tx_byte),
      .tx_load   (tx_load),
      .cs_active (cs_active)
  );

  // Register File instance
  reg_file u_regs (
      .clk           (clk),
      .rst_n         (rst_n),
      .rx_byte       (rx_byte),
      .rx_valid      (rx_valid),
      .cs_active     (cs_active),
      .tx_byte       (tx_byte),
      .tx_load       (tx_load),
      .acc_out       (acc_out),
      .act_out       (act_out),
      .overflow      (overflow),
      .busy          (busy),
      .start_compute (start_compute),
      .rst_acc       (rst_acc),
      .mode          (mode),
      .act_en        (act_en),
      .weights       (weights),
      .activations   (activations),
      .irq           (irq)
  );

  // Compute Datapath instance
  dot_product_engine u_engine (
      .clk           (clk),
      .rst_n         (rst_n),
      .start_compute (start_compute),
      .rst_acc       (rst_acc),
      .mode          (mode),
      .act_en        (act_en),
      .weights       (weights),
      .activations   (activations),
      .acc_out       (acc_out),
      .act_out       (act_out),
      .overflow      (overflow),
      .busy          (busy)
  );

  // Dedicated output pin mapping
  assign uo_out[0]   = miso;
  assign uo_out[1]   = busy;
  assign uo_out[2]   = irq;
  assign uo_out[7:3] = acc_out[23:19]; // Top 5 bits of accumulator for oscilloscope/debug

  // Bidirectional pins configured as safe high-Z inputs
  assign uio_out = 8'b00000000;
  assign uio_oe  = 8'b00000000;

  // List all unused inputs to prevent compiler warnings
  wire _unused = &{ena, ui_in[7:3], uio_in, 1'b0};

endmodule
