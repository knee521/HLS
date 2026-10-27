`timescale 1ns/1ps
`default_nettype none
module exp3_top #(
    parameter integer CLOCK_HZ=50000000,
    parameter integer BAUD=115200,
    parameter integer RIGHTMOST_INDEX=0,
    parameter integer CORE_TIMEOUT_CYCLES=1000000
)(
    input wire sys_clk, input wire sys_rst_n, input wire uart_rxd,
    output wire uart_txd, output wire [3:0] led,
    output wire [7:0] seg_led, output wire [5:0] seg_sel
);
    wire reset;
    reset_sync rst(.clk(sys_clk),.reset_n(sys_rst_n),.reset(reset));
    wire [7:0] rx_data;
    wire rx_valid, framing_error, memory_write, frame_valid, rejected;
    wire [9:0] write_address;
    wire [7:0] write_data;
    wire [15:0] frame_sequence;
    reg busy;
    uart_rx #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD)) receiver(
        .clk(sys_clk),.reset(reset),.rxd(uart_rxd),.data(rx_data),
        .valid(rx_valid),.framing_error(framing_error));
    frame_parser parser(.clk(sys_clk),.reset(reset),.enable(!busy),
        .rx_data(rx_data),.rx_valid(rx_valid),.framing_error(framing_error),
        .memory_write(memory_write),.memory_address(write_address),.memory_data(write_data),
        .frame_valid(frame_valid),.sequence_id(frame_sequence),.rejected(rejected));
    // One synchronous read port, one write port; parser ownership is disabled while busy.
    (* ram_style="block" *) reg [7:0] image_memory[0:1023];
    wire [9:0] read_address;
    wire read_enable;
    reg [7:0] read_data;
    always @(posedge sys_clk) begin
        if(memory_write && !busy) image_memory[write_address]<=write_data;
        if(read_enable) read_data<=image_memory[read_address];
    end
    reg core_start, core_reset;
    wire core_done, core_ready, core_idle;
    wire [3:0] core_result;
    nn_infer core(.ap_clk(sys_clk),.ap_rst(reset|core_reset),.ap_start(core_start),
        .ap_done(core_done),.ap_ready(core_ready),.ap_idle(core_idle),
        .image_V_address0(read_address),.image_V_ce0(read_enable),
        .image_V_q0(read_data),.ap_return(core_result));
    reg [3:0] last_digit;
    reg has_result;
    assign led=has_result ? last_digit : 4'b0000;
    seven_segment #(.CLOCK_HZ(CLOCK_HZ),.RIGHTMOST_INDEX(RIGHTMOST_INDEX)) display(
        .clk(sys_clk),.reset(reset),.digit(last_digit),.result_valid(has_result),
        .seg_led(seg_led),.seg_sel(seg_sel));
    reg response_start;
    reg [15:0] active_sequence;
    reg [31:0] timer, measured_cycles;
    reg [7:0] result_status, response_digit;
    wire [7:0] tx_data;
    wire tx_valid, tx_ready, queued_all;
    response_builder response(.clk(sys_clk),.reset(reset),.start(response_start),
        .sequence_id(active_sequence),.status(result_status),.digit(response_digit),
        .cycles(measured_cycles),.tx_data(tx_data),.tx_valid(tx_valid),
        .tx_ready(tx_ready),.queued_all(queued_all));
    uart_tx #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD)) transmitter(
        .clk(sys_clk),.reset(reset),.data(tx_data),.valid(tx_valid),.ready(tx_ready),.txd(uart_txd));
    localparam [1:0] IDLE=0, INFER=1, RESPOND=2, DRAIN=3;
    reg [1:0] state;
    always @(posedge sys_clk) begin
        if(reset) begin
            state<=IDLE; busy<=0; core_start<=0; core_reset<=0; response_start<=0;
            active_sequence<=0; timer<=0; measured_cycles<=0;
            result_status<=0; response_digit<=8'hff; last_digit<=0; has_result<=0;
        end else begin
            response_start<=0; core_reset<=0;
            case(state)
                IDLE: if(frame_valid && core_idle) begin
                    busy<=1; active_sequence<=frame_sequence;
                    core_start<=1; timer<=0; state<=INFER;
                end
                INFER: begin
                    timer<=timer+1;
                    if(core_ready) core_start<=0;
                    if(core_done) begin
                        core_start<=0; last_digit<=core_result; has_result<=1;
                        response_digit<={4'b0000,core_result}; result_status<=0;
                        measured_cycles<=timer+1; response_start<=1; state<=RESPOND;
                    end else if(timer>=CORE_TIMEOUT_CYCLES-1) begin
                        core_start<=0; core_reset<=1;
                        response_digit<=8'hff; result_status<=1;
                        measured_cycles<=timer+1; response_start<=1; state<=RESPOND;
                    end
                end
                RESPOND: if(queued_all) state<=DRAIN;
                DRAIN: if(tx_ready) begin busy<=0; state<=IDLE; end
                default: begin state<=IDLE; busy<=0; core_start<=0; core_reset<=1; end
            endcase
        end
    end
endmodule
`default_nettype wire

