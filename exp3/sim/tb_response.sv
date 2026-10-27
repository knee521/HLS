`timescale 1ns/1ps
module tb_response;
    reg clk=0; always #10 clk=~clk;
    reg reset=1,start=0,ready=0;
    wire [7:0] data;
    wire valid,done;
    reg [7:0] expected[0:16];
    integer count=0, ticks=0;
    response_builder dut(.clk(clk),.reset(reset),.start(start),.sequence_id(16'h1234),
        .status(8'h00),.digit(8'h07),.cycles(32'd25408),
        .tx_data(data),.tx_valid(valid),.tx_ready(ready),.queued_all(done));
    always @(negedge clk) begin ticks=ticks+1; ready=(ticks%3!=0); end
    always @(posedge clk) if(!reset && valid && ready) begin
        if(count>=17 || data!==expected[count]) $fatal(1,"Response byte %0d wrong",count);
        count=count+1;
    end
    initial begin
        expected[0]='ha5;expected[1]='h5a;expected[2]=1;expected[3]='h81;
        expected[4]='h34;expected[5]='h12;expected[6]=7;expected[7]=0;
        expected[8]=0;expected[9]=7;expected[10]=0;expected[11]='h40;
        expected[12]='h63;expected[13]=0;expected[14]=0;expected[15]='hea;expected[16]='hf5;
        repeat(5) @(negedge clk); reset=0;start=1;
        @(negedge clk);start=0;
        wait(done); @(negedge clk);
        if(count!=17) $fatal(1,"Wrong frame length");
        $display("TEST_PASS tb_response golden_crc_and_backpressure");$finish;
    end
    initial begin #100000; $fatal(1,"Response timeout"); end
endmodule
