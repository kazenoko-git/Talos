/*
 * Copyright (c) 2026 Ivan
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_kazenoko_talos (
    input wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input wire ena,      // Tile enable
    input wire clk,      // Clock (16 MHz)
    input wire rst_n     // Active-low asynchronous reset
);

  // Dedicated SPI inputs
  wire sclk = ui_in[0];
  wire mosi = ui_in[1];
  wire cs_n = ui_in[2];
  wire ext_tick_in = ui_in[3]; // hardware step tick pulse input

  // SPI signals
  wire miso;
  wire busy;
  wire [15:0] spikes_out;
  wire [127:0] v_mem_all;
  wire reg_step_tick;
  wire [1:0] leak_sel;
  wire signed [7:0] v_th;
  wire signed [7:0] weight_scale;
  wire [7:0] ext_spike_in;
  wire soft_rst;

  // Internal interconnect wires
  wire [7:0] rx_byte;
  wire rx_valid;
  wire cs_active;
  wire [7:0] tx_byte;
  wire tx_load;

  // edge detector on ui_in[3] to allow stepping via SPI or pin
  reg ext_tick_d;
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      ext_tick_d <= 1'b0;
    else
      ext_tick_d <= ext_tick_in;
  end
  wire ext_tick_pulse = ext_tick_in & ~ext_tick_d;
  wire step_tick = reg_step_tick | ext_tick_pulse;
  wire eff_rst_n = rst_n & ~soft_rst;

  // SPI Slave instance
  spi_slave u_spi (
      .clk (clk),
      .rst_n (rst_n),
      .sclk (sclk),
      .mosi (mosi),
      .cs_n (cs_n),
      .miso (miso),
      .rx_byte (rx_byte),
      .rx_valid (rx_valid),
      .tx_byte (tx_byte),
      .tx_load (tx_load),
      .cs_active (cs_active)
  );

  // Register File instance
  reg_file u_regs (
      .clk (clk),
      .rst_n (rst_n),
      .rx_byte (rx_byte),
      .rx_valid (rx_valid),
      .cs_active (cs_active),
      .tx_byte (tx_byte),
      .tx_load (tx_load),
      .busy (busy),
      .spikes_out (spikes_out),
      .v_mem_all (v_mem_all),
      .step_tick (reg_step_tick),
      .leak_sel (leak_sel),
      .v_th (v_th),
      .weight_scale (weight_scale),
      .ext_spike_in (ext_spike_in),
      .soft_rst (soft_rst)
  );

  // 16 Neuron Spiking Recurrent Reservoir Instance
  spiking_reservoir u_reservoir (
      .clk (clk),
      .rst_n (eff_rst_n),
      .step_tick (step_tick),
      .ext_spike_in (ext_spike_in),
      .v_th (v_th),
      .leak_sel (leak_sel),
      .weight_scale (weight_scale),
      .busy (busy),
      .spikes_out (spikes_out),
      .v_mem_all (v_mem_all)
  );

  // Dedicated output pin mapping
  assign uo_out[0] = miso;
  assign uo_out[7:1] = spikes_out[6:0]; // neurons 0..6 spikes on carrier board LEDs

  // Bidi pin map
  assign uio_out = spikes_out[15:8]; // neurons 8..15 spikes
  assign uio_oe = 8'hFF;             // enabled as outputs

  // List all unused inputs to prevent compiler warnings
  wire _unused = &{ena, ui_in[7:4], uio_in, 1'b0};

endmodule
