`timescale 1ns/1ps
module tb_display;
    reg clk=0;always #10 clk=~clk;
    reg reset=1;
    wire [7:0] seg;
    wire [5:0] sel;
    integer active=0, seen_startup=0;
    seven_segment #(.CLOCK_HZ(10000),.RIGHTMOST_INDEX(0)) dut(
        .clk(clk),.reset(reset),.digit(4'd7),.result_valid(1'b1),.seg_led(seg),.seg_sel(sel));
    always @(negedge clk) if(!reset) begin
        if(!$onehot0(~sel)) $fatal(1,"Multiple digit enables");
        if(dut.startup && sel!=6'b111111) begin
            if(seg!=8'h80) $fatal(1,"Startup segment code");
            seen_startup=1;
        end
        if(!dut.startup && dut.startup_count>0 && $time>202000 && sel!=6'b111111) begin
            if(sel!=6'b111110 || seg!=8'hf8) $fatal(1,"Rightmost display mapping");
            active=active+1;
        end
    end
    initial begin
        repeat(5) @(negedge clk);reset=0;
        repeat(11000) @(negedge clk);
        if(!seen_startup || active==0) $fatal(1,"No display coverage");
        $display("TEST_PASS tb_display polarity_scanning_blank_slot");$finish;
    end
endmodule
