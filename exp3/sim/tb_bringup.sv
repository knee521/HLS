`timescale 1ns/1ps
// Exercise the actual echo FIFO with a PC clock independent of the FPGA divider.
module tb_bringup;
    reg clk=0; always #10 clk=~clk;
    reg reset_n=0, pc_tx=1;
    wire fpga_tx;
    wire [3:0] led;
    wire [7:0] segments;
    wire [5:0] selects;
    bringup_top dut(.sys_clk(clk),.sys_rst_n(reset_n),.uart_rxd(pc_tx),
        .uart_txd(fpga_tx),.led(led),.seg_led(segments),.seg_sel(selects));
    wire [7:0] received;
    wire valid, error;
    uart_rx monitor(.clk(clk),.reset(!reset_n),.rxd(fpga_tx),
        .data(received),.valid(valid),.framing_error(error));
    integer rx_count=0, echo_count=0, mismatches=0, errors=0, high_water=0;
    integer i,b,bit_ns;
    always @(posedge clk) if(reset_n) begin
        if(dut.rx_valid) rx_count=rx_count+1;
        if(dut.rx_error || error) errors=errors+1;
        if(dut.count>high_water) high_water=dut.count;
        if(valid) begin
            if(received !== (echo_count % 256)) mismatches=mismatches+1;
            echo_count=echo_count+1;
        end
    end
    task run_burst;
        input integer period_ns;
        begin
            @(negedge clk); reset_n=0; pc_tx=1;
            repeat(10) @(negedge clk);
            rx_count=0;echo_count=0;mismatches=0;errors=0;high_water=0;
            reset_n=1; repeat(10) @(negedge clk);
            // phase offset prevents PC edges from sharing FPGA clock edges.
            #7;
            for(i=0;i<2560;i=i+1) begin
                pc_tx=0; #(period_ns);
                for(b=0;b<8;b=b+1) begin pc_tx=(i>>b)&1; #(period_ns); end
                pc_tx=1; #(period_ns);
            end
            #30000000;
            $display("ECHO_BURST bit_ns=%0d rx=%0d echo=%0d mismatch=%0d errors=%0d high_water=%0d overflow=%0d",
                period_ns,rx_count,echo_count,mismatches,errors,high_water,dut.overflow);
            if(rx_count!=2560 || echo_count!=2560 || mismatches!=0 || errors!=0 || dut.overflow)
                $fatal(1,"Continuous echo lost/corrupted bytes under independent UART timing");
        end
    endtask
    initial begin
        run_burst(8681);  // nominal 115200, rounded to nanoseconds
        run_burst(8605);  // about 0.88 percent faster: exercises small burst accumulation
        run_burst(8510);  // approximately 2 percent faster; still valid UART sampling
        run_burst(8854);  // approximately 2 percent slower
        $display("TEST_PASS tb_bringup 4x2560_bytes_independent_baud_plus_minus_2pct");
        $finish;
    end
    initial begin #1300000000; $fatal(1,"Echo test timeout"); end
endmodule
