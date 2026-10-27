`timescale 1ns/1ps
`default_nettype none
// Hardware-only first-stage image: buffered UART echo plus cycling display digits.
module bringup_top #(
    parameter integer CLOCK_HZ=50000000,
    parameter integer BAUD=115200,
    parameter integer RIGHTMOST_INDEX=0
)(
    input wire sys_clk, input wire sys_rst_n, input wire uart_rxd,
    output wire uart_txd, output wire [3:0] led,
    output wire [7:0] seg_led, output wire [5:0] seg_sel
);
    wire reset, rx_valid, rx_error, tx_ready;
    wire [7:0] rx_data;
    reset_sync rst(.clk(sys_clk),.reset_n(sys_rst_n),.reset(reset));
    uart_rx #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD)) rx(.clk(sys_clk),.reset(reset),
        .rxd(uart_rxd),.data(rx_data),.valid(rx_valid),.framing_error(rx_error));
    reg [7:0] fifo[0:15];
    reg [3:0] read_pointer, write_pointer;
    reg [4:0] count;
    reg overflow;
    wire pop=(count!=0) && tx_ready;
    wire push=rx_valid && (count<16 || pop);
    uart_tx #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD)) tx(.clk(sys_clk),.reset(reset),
        .data(fifo[read_pointer]),.valid(count!=0),.ready(tx_ready),.txd(uart_txd));
    reg [31:0] second_counter;
    reg [3:0] digit;
    assign led=overflow ? 4'hf : digit;
    seven_segment #(.CLOCK_HZ(CLOCK_HZ),.RIGHTMOST_INDEX(RIGHTMOST_INDEX),.DIAGNOSTIC(1)) display(
        .clk(sys_clk),.reset(reset),.digit(digit),.result_valid(1'b1),
        .seg_led(seg_led),.seg_sel(seg_sel));
    always @(posedge sys_clk) begin
        if(reset) begin
            read_pointer<=0; write_pointer<=0; count<=0; overflow<=0;
            second_counter<=0; digit<=0;
        end else begin
            if(rx_valid && !push) overflow<=1;
            if(push) begin fifo[write_pointer]<=rx_data; write_pointer<=write_pointer+1; end
            if(pop) read_pointer<=read_pointer+1;
            case({push,pop})
                2'b10:count<=count+1;
                2'b01:count<=count-1;
                default:count<=count;
            endcase
            if(second_counter==CLOCK_HZ-1) begin
                second_counter<=0; digit<=digit==9 ? 0 : digit+1;
            end else second_counter<=second_counter+1;
        end
    end
endmodule
`default_nettype wire

