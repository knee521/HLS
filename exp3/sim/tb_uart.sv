`timescale 1ns/1ps
module tb_uart;
    reg clk=0;
    always #10 clk=~clk;
    reg reset=1;
    reg [7:0] tx_data=0;
    reg tx_valid=0;
    wire ready, line, received, error;
    wire [7:0] rx_data;
    reg inject_bad_stop=0;
    wire rx_line = inject_bad_stop ? 1'b0 : line;
    integer sent=0, count=0, errors=0;
    uart_tx tx(.clk(clk),.reset(reset),.data(tx_data),.valid(tx_valid),.ready(ready),.txd(line));
    uart_rx rx(.clk(clk),.reset(reset),.rxd(rx_line),.data(rx_data),.valid(received),.framing_error(error));
    always @(posedge clk) begin
        if (!reset && received) begin
            if (rx_data !== (count % 256)) $fatal(1,"RX mismatch index %0d got %0d",count,rx_data);
            count=count+1;
        end
        if (error) errors=errors+1;
    end
    initial begin
        repeat(5) @(negedge clk);
        reset=0;
        for(sent=0;sent<2560;sent=sent+1) begin
            wait(ready);
            @(negedge clk); tx_data=sent%256; tx_valid=1;
            @(negedge clk); tx_valid=0;
            wait(!ready); wait(ready);
        end
        repeat(10) @(negedge clk);
        if (count!=2560 || errors!=0) $fatal(1,"UART normal transfer failed");
        inject_bad_stop=1;
        repeat(434*11) @(negedge clk);
        inject_bad_stop=0;
        repeat(434*12) @(negedge clk);
        if (errors==0) $fatal(1,"Missing framing error");
        // Return to a normal transaction after the malformed stop bit.
        wait(ready); @(negedge clk); tx_data=0; tx_valid=1;
        @(negedge clk); tx_valid=0;
        wait(!ready); wait(ready);
        repeat(10) @(negedge clk);
        if(count!=2561) $fatal(1,"No recovery after framing error");
        $display("TEST_PASS tb_uart bytes=2561 framing_errors=%0d",errors);
        $finish;
    end
    initial begin #500000000; $fatal(1,"UART simulation timeout"); end
endmodule

