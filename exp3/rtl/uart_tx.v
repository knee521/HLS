`timescale 1ns/1ps
`default_nettype none
module uart_tx #(
    parameter integer CLOCK_HZ = 50000000,
    parameter integer BAUD = 115200
)(
    input wire clk, input wire reset,
    input wire [7:0] data, input wire valid,
    output wire ready, output wire txd
);
    localparam integer DIVISOR = (CLOCK_HZ + BAUD/2) / BAUD;
    reg [31:0] timer;
    reg [9:0] shift;
    reg [3:0] bits_left;
    assign ready = (bits_left == 0);
    assign txd = ready ? 1'b1 : shift[0];
    always @(posedge clk) begin
        if (reset) begin
            timer <= 0; shift <= 10'h3ff; bits_left <= 0;
        end else if (ready) begin
            if (valid) begin
                shift <= {1'b1, data, 1'b0};
                bits_left <= 10;
                timer <= DIVISOR - 1;
            end
        end else if (timer != 0) begin
            timer <= timer - 1;
        end else begin
            timer <= DIVISOR - 1;
            shift <= {1'b1, shift[9:1]};
            bits_left <= bits_left - 1;
        end
    end
endmodule
`default_nettype wire

