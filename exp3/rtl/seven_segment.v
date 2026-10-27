`timescale 1ns/1ps
`default_nettype none
module seven_segment #(
    parameter integer CLOCK_HZ=50000000,
    parameter integer RIGHTMOST_INDEX=0,
    parameter integer DIAGNOSTIC=0
)(
    input wire clk, input wire reset,
    input wire [3:0] digit, input wire result_valid,
    output reg [7:0] seg_led, output reg [5:0] seg_sel
);
    localparam integer SLOT_CYCLES = CLOCK_HZ/1000;
    reg [31:0] startup_count, slot_count;
    reg [31:0] diagnostic_timer;
    reg [4:0] diagnostic_step;
    reg [2:0] position;
    wire startup = startup_count < CLOCK_HZ;
    function [7:0] segments;
        input [3:0] value;
        begin
            case(value)
                // Board pins are {dp,g,f,e,d,c,b,a}, active low.
                0: segments=8'hc0; 1: segments=8'hf9;
                2: segments=8'ha4; 3: segments=8'hb0;
                4: segments=8'h99; 5: segments=8'h92;
                6: segments=8'h82; 7: segments=8'hf8;
                8: segments=8'h80; 9: segments=8'h90;
                default: segments=8'hbf;
            endcase
        end
    endfunction
    always @(posedge clk) begin
        if (reset) begin
            startup_count<=0; slot_count<=0; position<=0;
            diagnostic_timer<=0; diagnostic_step<=0;
            seg_led<=8'hff; seg_sel<=6'b111111;
        end else begin
            if (startup) startup_count<=startup_count+1;
            if (DIAGNOSTIC) begin
                if(diagnostic_timer==CLOCK_HZ-1) begin
                    diagnostic_timer<=0;
                    diagnostic_step<=diagnostic_step==24 ? 0 : diagnostic_step+1;
                end else diagnostic_timer<=diagnostic_timer+1;
            end
            if (slot_count == SLOT_CYCLES-1) begin
                slot_count<=0;
                position <= position==5 ? 0 : position+1;
            end else slot_count<=slot_count+1;
            if (slot_count==0) seg_sel<=6'b111111;
            if (slot_count==1) begin
                if(DIAGNOSTIC) begin
                    if(diagnostic_step==0) seg_led<=segments(8);
                    else if(diagnostic_step<=6) seg_led<=segments(diagnostic_step-1);
                    else if(diagnostic_step<=14) seg_led<=~(8'h01 << (diagnostic_step-7));
                    else seg_led<=segments(diagnostic_step-15);
                end else seg_led <= startup ? segments(8) :
                    (result_valid ? segments(digit) : 8'hbf);
            end
            if (slot_count==2) begin
                if(DIAGNOSTIC) begin
                    if(diagnostic_step==0 ||
                       (diagnostic_step>=1 && diagnostic_step<=6 && position==diagnostic_step-1) ||
                       (diagnostic_step>=7 && position==RIGHTMOST_INDEX))
                        seg_sel<=~(6'b000001 << position);
                    else seg_sel<=6'b111111;
                end else if (startup || position==RIGHTMOST_INDEX)
                    seg_sel <= ~(6'b000001 << position);
                else seg_sel <= 6'b111111;
            end
        end
    end
endmodule
`default_nettype wire

