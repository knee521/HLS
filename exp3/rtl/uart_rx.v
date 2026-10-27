`timescale 1ns/1ps
`default_nettype none
module uart_rx #(
    parameter integer CLOCK_HZ = 50000000,
    parameter integer BAUD = 115200
)(
    input wire clk, input wire reset, input wire rxd,
    output reg [7:0] data, output reg valid, output reg framing_error
);
    localparam integer DIVISOR = (CLOCK_HZ + BAUD/2) / BAUD;
    localparam [2:0] IDLE=0, START=1, DATA=2, STOP=3, WAIT_HIGH=4;
    (* ASYNC_REG = "TRUE" *) reg [1:0] synchronizer;
    reg [2:0] state;
    reg [31:0] timer;
    reg [2:0] bit_index;
    reg [7:0] shift;
    always @(posedge clk) begin
        if (reset) synchronizer <= 2'b11;
        else synchronizer <= {synchronizer[0], rxd};
    end
    always @(posedge clk) begin
        if (reset) begin
            state <= IDLE; timer <= 0; bit_index <= 0;
            data <= 0; shift <= 0; valid <= 0; framing_error <= 0;
        end else begin
            valid <= 0;
            framing_error <= 0;
            case (state)
                IDLE: if (!synchronizer[1]) begin
                    timer <= DIVISOR/2 - 1; state <= START;
                end
                START: if (timer != 0) timer <= timer - 1;
                else if (synchronizer[1]) state <= IDLE;
                else begin timer <= DIVISOR - 1; bit_index <= 0; state <= DATA; end
                DATA: if (timer != 0) timer <= timer - 1;
                else begin
                    shift[bit_index] <= synchronizer[1];
                    timer <= DIVISOR - 1;
                    if (bit_index == 7) state <= STOP;
                    else bit_index <= bit_index + 1;
                end
                STOP: if (timer != 0) timer <= timer - 1;
                else begin
                    if (synchronizer[1]) begin
                        data <= shift; valid <= 1; state <= IDLE;
                    end else begin
                        framing_error <= 1; state <= WAIT_HIGH;
                    end
                end
                // A break must return to idle-high before a new start bit is accepted.
                WAIT_HIGH: if (synchronizer[1]) state <= IDLE;
                default: state <= IDLE;
            endcase
        end
    end
endmodule
`default_nettype wire

