`timescale 1ns/1ps
module tb_parser;
    reg clk=0; always #10 clk=~clk;
    reg reset=1, enable=1, rx_valid=0, framing_error=0;
    reg [7:0] rx_data=0;
    wire wr, good, rejected;
    wire [9:0] address;
    wire [7:0] data;
    wire [15:0] seq;
    integer accepted=0, writes=0, rejections=0, i, attempt;
    reg [15:0] crc;
    reg [7:0] memory[0:783];
    function [7:0] pixel_value;
        input integer index;
        begin
            if(index%100==0) pixel_value=8'ha5;
            else if(index%100==1) pixel_value=8'h5a;
            else pixel_value=index%256;
        end
    endfunction
    frame_parser #(.BYTE_TIMEOUT_CYCLES(50),.FRAME_TIMEOUT_CYCLES(10000)) dut(
        .clk(clk),.reset(reset),.enable(enable),.rx_data(rx_data),.rx_valid(rx_valid),
        .framing_error(framing_error),.memory_write(wr),.memory_address(address),
        .memory_data(data),.frame_valid(good),.sequence_id(seq),.rejected(rejected));
    function [15:0] update_crc;
        input [15:0] previous; input [7:0] value;
        reg [15:0] c; integer b;
        begin
            c=previous^{value,8'h00};
            for(b=0;b<8;b=b+1) c=c[15] ? (c<<1)^16'h1021 : c<<1;
            update_crc=c;
        end
    endfunction
    task send;
        input [7:0] value;
        begin
            @(negedge clk); rx_data=value; rx_valid=1;
            @(negedge clk); rx_valid=0;
        end
    endtask
    task checked;
        input [7:0] value;
        begin send(value); crc=update_crc(crc,value); end
    endtask
    task packet;
        input corrupt;
        begin
            send(8'ha5); send(8'h5a); crc=16'hffff;
            checked(1); checked(1); checked(8'h34); checked(8'h12);
            checked(8'h10); checked(3);
            for(i=0;i<784;i=i+1) checked(pixel_value(i));
            send(crc[7:0]); send(crc[15:8] ^ corrupt);
            repeat(3) @(negedge clk);
        end
    endtask
    always @(posedge clk) begin
        if(wr) begin
            if(address>783) $fatal(1,"RAM address overflow");
            memory[address]=data; writes=writes+1;
        end
        if(good) begin
            accepted=accepted+1;
            if(seq!=16'h1234) $fatal(1,"Sequence endian mismatch");
        end
        if(rejected) rejections=rejections+1;
    end
    initial begin
        repeat(5) @(negedge clk); reset=0;
        send(8'ha5); packet(0); // overlapping A5 A5 5A
        if(accepted!=1 || writes!=784) $fatal(1,"Normal frame not accepted");
        for(i=0;i<784;i=i+1) if(memory[i] !== pixel_value(i)) $fatal(1,"RAM data mismatch");
        packet(1);
        if(accepted!=1) $fatal(1,"CRC failure accepted");
        // Invalid lengths, versions, partial payload, framing error and busy discard.
        for(attempt=0;attempt<4;attempt=attempt+1) begin
            send(8'ha5); send(8'h5a); send(1); send(1); send(0); send(0);
            case(attempt)
                0:begin send(0); send(0); end
                1:begin send(8'h0f); send(3); end
                2:begin send(8'h11); send(3); end
                3:begin send(8'hff); send(8'hff); end
            endcase
        end
        send(8'ha5);send(8'h5a);send(2);
        send(8'ha5);send(8'h5a);send(1);send(8'h7f);
        send(8'ha5);send(8'h5a);send(1);
        repeat(55) @(negedge clk);
        send(8'ha5);send(8'h5a);send(1);
        @(negedge clk); framing_error=1;
        @(negedge clk); framing_error=0;
        enable=0; packet(0); enable=1;
        if(accepted!=1) $fatal(1,"Busy or invalid frame accepted");
        // Keep each gap below the inter-byte limit but exceed the total-frame deadline.
        send(8'ha5);send(8'h5a);send(1);send(1);send(0);send(0);send('h10);send(3);
        for(i=0;i<300;i=i+1) begin send(0); repeat(40) @(negedge clk); end
        packet(0);
        if(accepted!=2 || rejections<8) $fatal(1,"Recovery coverage failed");
        $display("TEST_PASS tb_parser accepted=%0d rejected=%0d",accepted,rejections);
        $finish;
    end
    initial begin #2000000; $fatal(1,"Parser simulation timeout"); end
endmodule

