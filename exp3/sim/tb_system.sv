`timescale 1ns/1ps
module tb_system;
    localparam integer BAUD=921600;
    localparam integer DIV=(50000000+BAUD/2)/BAUD;
    reg clk=0; always #10 clk=~clk;
    reg rst_n=0,rxd=1;
    wire txd;
    wire [3:0] led;
    wire [7:0] seg;
    wire [5:0] sel;
    exp3_top #(.BAUD(BAUD)) dut(.sys_clk(clk),.sys_rst_n(rst_n),.uart_rxd(rxd),
        .uart_txd(txd),.led(led),.seg_led(seg),.seg_sel(sel));
    wire [7:0] response_byte;
    wire response_valid,response_error;
    uart_rx #(.BAUD(BAUD)) monitor(.clk(clk),.reset(!rst_n),.rxd(txd),
        .data(response_byte),.valid(response_valid),.framing_error(response_error));
    reg [7:0] pixels[0:783], reference[0:23], reply[0:16];
    integer response_index=0, responses=0, sample=0, p, k;
    reg [15:0] crc, reply_crc;
    function [15:0] crc_step;
        input [15:0] previous; input [7:0] value;
        integer b; reg [15:0] c;
        begin
            c=previous^{value,8'h00};
            for(b=0;b<8;b=b+1) c=c[15] ? (c<<1)^16'h1021 : c<<1;
            crc_step=c;
        end
    endfunction
    task send_byte;
        input [7:0] value; integer b;
        begin
            @(negedge clk); rxd=0; repeat(DIV) @(negedge clk);
            for(b=0;b<8;b=b+1) begin rxd=value[b]; repeat(DIV) @(negedge clk); end
            rxd=1; repeat(DIV) @(negedge clk);
        end
    endtask
    task checked_byte;
        input [7:0] value;
        begin send_byte(value);crc=crc_step(crc,value);end
    endtask
    task send_frame;
        input corrupt;
        begin
            send_byte('ha5);send_byte('h5a);crc='hffff;
            checked_byte(1);checked_byte(1);checked_byte(sample);checked_byte(0);
            checked_byte('h10);checked_byte(3);
            for(p=0;p<784;p=p+1) checked_byte(pixels[p]);
            send_byte(crc[7:0]);send_byte(crc[15:8]^corrupt);
        end
    endtask
    always @(posedge clk) if(rst_n) begin
        if(response_error) $fatal(1,"Response UART framing error");
        if(dut.busy && dut.memory_write) $fatal(1,"Image RAM written during inference");
        if(response_valid) begin
            reply[response_index]=response_byte;
            if(response_index==16) begin
                reply_crc='hffff;
                for(k=2;k<15;k=k+1) reply_crc=crc_step(reply_crc,reply[k]);
                if(reply[0]!='ha5 || reply[1]!='h5a || reply[2]!=1 || reply[3]!='h81 ||
                   reply[4]!=sample || reply[5]!=0 || reply[6]!=7 || reply[7]!=0 ||
                   reply[8]!=0 || reply[9]!=reference[2*sample] || reply[10]!=0 ||
                   {reply[16],reply[15]}!=reply_crc)
                    $fatal(1,"System response mismatch sample=%0d digit=%0d expected=%0d",
                        sample,reply[9],reference[2*sample]);
                if(led!==reference[2*sample][3:0]) $fatal(1,"LED result mismatch");
                if({reply[14],reply[13],reply[12],reply[11]}<26364 ||
                   {reply[14],reply[13],reply[12],reply[11]}>26370)
                    $fatal(1,"Core cycle accounting mismatch");
                responses=responses+1;response_index=0;
                $display("SYSTEM_SAMPLE sample=%0d digit=%0d cycles=%0d",sample,reply[9],
                    {reply[14],reply[13],reply[12],reply[11]});
            end else response_index=response_index+1;
        end
    end
    initial begin
        $readmemh("cosim_predictions.hex",reference);
        repeat(5) @(negedge clk);rst_n=1;
        repeat(5) @(negedge clk);
        for(sample=0;sample<10;sample=sample+1) begin
            $readmemh($sformatf("sample_%02d.hex",2*sample),pixels);
            if(sample==0) begin
                send_frame(1);repeat(100000) @(negedge clk);
                if(responses!=0 || dut.has_result) $fatal(1,"Bad CRC triggered inference");
            end
            send_frame(0);
            wait(responses==sample+1);
            wait(!dut.busy);
            repeat(10) @(negedge clk);
        end
        $display("TEST_PASS tb_system real_hls_core_10_digits_crc_cycles_led");$finish;
    end
    initial begin #500000000; $fatal(1,"System simulation timeout");end
endmodule

