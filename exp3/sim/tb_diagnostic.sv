`timescale 1ns/1ps
module tb_diagnostic;
    reg clk=0;always #10 clk=~clk;
    reg reset=1;
    wire [7:0] seg;
    wire [5:0] sel;
    reg [24:0] observed=0;
    integer phase;
    seven_segment #(.CLOCK_HZ(10000),.RIGHTMOST_INDEX(0),.DIAGNOSTIC(1)) dut(
        .clk(clk),.reset(reset),.digit(4'd0),.result_valid(1'b1),.seg_led(seg),.seg_sel(sel));
    always @(negedge clk) if(!reset && dut.diagnostic_timer>100 && sel!=6'b111111) begin
        phase=dut.diagnostic_step;
        observed[phase]=1;
        if(!$onehot0(~sel)) $fatal(1,"Diagnostic selected multiple digits");
        if(phase==0 && seg!=8'h80) $fatal(1,"Diagnostic all-eight phase");
        if(phase>=1 && phase<=6 && sel!=~(6'b000001<<(phase-1)))
            $fatal(1,"Diagnostic position phase");
        if(phase>=7 && phase<=14 && seg!=~(8'h01<<(phase-7)))
            $fatal(1,"Diagnostic segment phase");
        if(phase>=7 && sel!=6'b111110) $fatal(1,"Diagnostic rightmost selection");
    end
    initial begin
        repeat(5)@(negedge clk);reset=0;
        repeat(250000)@(negedge clk);
        if(observed!=25'h1ffffff) $fatal(1,"Missing diagnostic phases");
        $display("TEST_PASS tb_diagnostic six_positions_eight_segments_ten_digits");$finish;
    end
endmodule
