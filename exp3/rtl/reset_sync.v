`timescale 1ns/1ps
`default_nettype none
// External reset asserts asynchronously; internal reset releases on a clock edge.
module reset_sync(input wire clk, input wire reset_n, output wire reset);
    (* ASYNC_REG = "TRUE" *) reg [1:0] sync_ff;
    always @(posedge clk or negedge reset_n)
        if (!reset_n) sync_ff <= 2'b11;
        else sync_ff <= {sync_ff[0], 1'b0};
    assign reset = sync_ff[1];
endmodule
`default_nettype wire

