/*
 * Copyright (c) 2026 Ivan
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module reg_file (
    input  wire              clk,
    input  wire              rst_n,

    // SPI slave interface
    input  wire [7:0]        rx_byte,
    input  wire              rx_valid,
    input  wire              cs_active,
    output reg  [7:0]        tx_byte,
    output reg               tx_load,

    // Spiking reservoir interface
    input  wire [15:0]       spikes_out,
    input  wire [127:0]      v_mem_all,
    output reg               step_tick,
    output reg  [1:0]        leak_sel,
    output reg  signed [7:0] v_th,
    output reg  signed [7:0] weight_scale,
    output reg  [7:0]        ext_spike_in,
    output reg               soft_rst
);

    localparam STATE_IDLE = 1'b0;
    localparam STATE_DATA = 1'b1;

    reg       state;
    reg       is_read;
    reg [6:0] current_addr;

    // Helper to read register data
    function [7:0] get_reg_data(input [6:0] addr);
        if (addr == 7'h00)
            get_reg_data = {4'b0, 1'b0, leak_sel, 1'b0};
        else if (addr == 7'h01)
            get_reg_data = v_th;
        else if (addr == 7'h02)
            get_reg_data = weight_scale;
        else if (addr == 7'h03)
            get_reg_data = ext_spike_in;
        else if (addr == 7'h04)
            get_reg_data = spikes_out[7:0];
        else if (addr == 7'h05)
            get_reg_data = spikes_out[15:8];
        else if (addr >= 7'h10 && addr <= 7'h1F)
            get_reg_data = v_mem_all[(addr - 7'h10)*8 +: 8];
        else
            get_reg_data = 8'h00;
    endfunction

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state        <= STATE_IDLE;
            is_read      <= 1'b0;
            current_addr <= 7'd0;
            tx_byte      <= 8'd0;
            tx_load      <= 1'b0;
            step_tick    <= 1'b0;
            leak_sel     <= 2'b10;    // Default: >>2 (25% decay)
            v_th         <= 8'sd32;   // Default threshold: +32
            weight_scale <= 8'sd12;   // Default weight: +12
            ext_spike_in <= 8'h00;
            soft_rst     <= 1'b0;
        end else if (!cs_active) begin
            state        <= STATE_IDLE;
            tx_load      <= 1'b0;
            step_tick    <= 1'b0;
            soft_rst     <= 1'b0;
        end else begin
            // Default 1-cycle strobes
            tx_load   <= 1'b0;
            step_tick <= 1'b0;
            soft_rst  <= 1'b0;

            case (state)
                STATE_IDLE: begin
                    if (rx_valid) begin
                        is_read      <= rx_byte[7];
                        current_addr <= rx_byte[6:0];
                        state        <= STATE_DATA;

                        if (rx_byte[7]) begin
                            tx_byte <= get_reg_data(rx_byte[6:0]);
                            tx_load <= 1'b1;
                        end
                    end
                end

                STATE_DATA: begin
                    if (rx_valid) begin
                        if (is_read) begin
                            current_addr <= current_addr + 7'd1;
                            tx_byte      <= get_reg_data(current_addr + 7'd1);
                            tx_load      <= 1'b1;
                        end else begin
                            case (current_addr)
                                7'h00: begin
                                    step_tick <= rx_byte[0];
                                    leak_sel  <= rx_byte[2:1];
                                    soft_rst  <= rx_byte[3];
                                end
                                7'h01: v_th         <= rx_byte;
                                7'h02: weight_scale <= rx_byte;
                                7'h03: ext_spike_in <= rx_byte;
                                default: ;
                            endcase
                        end
                    end
                end
            endcase
        end
    end

endmodule
