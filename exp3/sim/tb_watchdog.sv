`timescale 1ns/1ps
module tb_watchdog;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,inject_valid=0;
    reg [7:0] inject_data=0;
    wire txd;
    wire [3:0] led;
    wire [7:0] seg;
    wire [5:0] sel;
    exp3_top #(.BAUD(921600),.CORE_TIMEOUT_CYCLES(30000)) dut(
        .sys_clk(clk),.sys_rst_n(rst_n),.uart_rxd(1'b1),.uart_txd(txd),
        .led(led),.seg_led(seg),.seg_sel(sel));
    wire [7:0] response;
    wire valid,framing_error;
    uart_rx #(.BAUD(921600)) monitor(.clk(clk),.reset(!rst_n),.rxd(txd),
        .data(response),.valid(valid),.framing_error(framing_error));
    reg [7:0] pixels[0:783], reply[0:16];
    reg [15:0] crc, check_crc;
    integer index=0, replies=0, i,j, transaction=0;
    function [15:0] step_crc;
        input [15:0] old;input [7:0] value;reg [15:0] c;integer b;
        begin
            c=old^{value,8'h00};
            for(b=0;b<8;b=b+1)c=c[15]?(c<<1)^16'h1021:c<<1;
            step_crc=c;
        end
    endfunction
    task send;
        input [7:0] value;
        begin
            @(negedge clk);inject_data=value;inject_valid=1;
            @(negedge clk);inject_valid=0;
        end
    endtask
    task checked;
        input [7:0] value;
        begin send(value);crc=step_crc(crc,value);end
    endtask
    task packet;
        begin
            send('ha5);send('h5a);crc='hffff;
            checked(1);checked(1);checked(transaction);checked(0);checked('h10);checked(3);
            for(i=0;i<784;i=i+1)checked(pixels[i]);
            send(crc[7:0]);send(crc[15:8]);
        end
    endtask
    task reset_device;
        begin
            @(negedge clk);rst_n=0;index=0;
            repeat(5)@(negedge clk);rst_n=1;
            repeat(5)@(negedge clk);
        end
    endtask
    always @(posedge clk) if(rst_n) begin
        if(framing_error) $fatal(1,"Reply framing error");
        if(dut.busy && dut.memory_write) $fatal(1,"RAM changed while busy");
        if(valid) begin
            reply[index]=response;
            if(index==16) begin
                check_crc='hffff;
                for(j=2;j<15;j=j+1)check_crc=step_crc(check_crc,reply[j]);
                if({reply[16],reply[15]}!=check_crc || reply[4]!=transaction)
                    $fatal(1,"Malformed watchdog response");
                if(transaction==0) begin
                    if(reply[8]!=1 || reply[9]!=255 || dut.has_result)
                        $fatal(1,"Watchdog did not reject stalled core");
                end else if(reply[8]!=0 || reply[9]!=1 || led!=1)
                    $fatal(1,"Recovery inference failed");
                index=0;replies=replies+1;
            end else index=index+1;
        end
    end
    initial begin
        $readmemh("sample_02.hex",pixels);
        force dut.rx_data=inject_data;
        force dut.rx_valid=inject_valid;
        repeat(5)@(negedge clk);rst_n=1;repeat(5)@(negedge clk);
        force dut.core_done=1'b0;
        packet();
        wait(dut.busy);
        // Deliberate input traffic while locked must not overwrite the image.
        repeat(10)send(8'hff);
        wait(replies==1);wait(!dut.busy);
        release dut.core_done;
        transaction=1;packet();wait(replies==2);wait(!dut.busy);
        // Reset during reception must discard the partial image.
        send('ha5);send('h5a);send(1);
        @(negedge clk);rst_n=0;repeat(5)@(negedge clk);rst_n=1;
        repeat(5)@(negedge clk);
        transaction=2;packet();wait(replies==3);wait(!dut.busy);
        // Reset a running HLS transaction, then require a complete fresh result.
        transaction=3;packet();wait(dut.busy);repeat(100)@(negedge clk);
        reset_device();
        transaction=4;packet();wait(replies==4);wait(!dut.busy);
        // Reset during a partial UART response; discard its partial host frame.
        transaction=5;packet();wait(index==5);
        reset_device();
        transaction=6;packet();wait(replies==5);wait(!dut.busy);
        $display("TEST_PASS tb_watchdog timeout_busy_reset_recovery");$finish;
    end
    initial begin #10000000;$fatal(1,"Watchdog test timeout");end
endmodule
