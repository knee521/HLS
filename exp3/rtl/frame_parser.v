`timescale 1ns/1ps
`default_nettype none
module frame_parser #(
    parameter integer BYTE_TIMEOUT_CYCLES=2500000,
    parameter integer FRAME_TIMEOUT_CYCLES=12500000
)(
    input wire clk, input wire reset, input wire enable,
    input wire [7:0] rx_data, input wire rx_valid, input wire framing_error,
    output reg memory_write, output reg [9:0] memory_address,
    output reg [7:0] memory_data, output reg frame_valid,
    output reg [15:0] sequence_id, output reg rejected
);
    localparam [2:0] SEARCH_A5=0, SEARCH_5A=1, HEADER=2, PAYLOAD=3, CRC_LOW=4, CRC_HIGH=5;
    reg [2:0] state, header_index;
    reg [9:0] payload_index;
    reg [7:0] received_crc_low;
    reg [15:0] crc;
    wire [15:0] next_crc;
    reg [31:0] byte_timer, frame_timer;
    crc16_byte update_crc(.crc(crc),.data(rx_data),.next_crc(next_crc));
    always @(posedge clk) begin
        if(reset) begin
            state<=SEARCH_A5; header_index<=0; payload_index<=0;
            crc<=16'hffff; received_crc_low<=0;
            memory_write<=0; memory_address<=0; memory_data<=0;
            frame_valid<=0; sequence_id<=0; rejected<=0;
            byte_timer<=0; frame_timer<=0;
        end else begin
            memory_write<=0; frame_valid<=0; rejected<=0;
            if(!enable) begin
                state<=SEARCH_A5; byte_timer<=0; frame_timer<=0;
            end else if(framing_error ||
                (state>=HEADER && (byte_timer>=BYTE_TIMEOUT_CYCLES-1 ||
                                    frame_timer>=FRAME_TIMEOUT_CYCLES-1))) begin
                state<=SEARCH_A5; byte_timer<=0; frame_timer<=0; rejected<=1;
            end else begin
                if(state>=HEADER) begin
                    frame_timer<=frame_timer+1;
                    byte_timer<=rx_valid ? 0 : byte_timer+1;
                end else begin frame_timer<=0; byte_timer<=0; end
                if(rx_valid) begin
                    case(state)
                        SEARCH_A5: if(rx_data==8'ha5) state<=SEARCH_5A;
                        SEARCH_5A: begin
                            if(rx_data==8'h5a) begin
                                state<=HEADER; header_index<=0; crc<=16'hffff;
                            end else if(rx_data!=8'ha5) state<=SEARCH_A5;
                        end
                        HEADER: begin
                            crc<=next_crc;
                            header_index<=header_index+1;
                            if((header_index==0 && rx_data!=1) ||
                               (header_index==1 && rx_data!=1) ||
                               (header_index==4 && rx_data!=8'h10) ||
                               (header_index==5 && rx_data!=8'h03)) begin
                                state<=SEARCH_A5; rejected<=1;
                            end else begin
                                if(header_index==2) sequence_id[7:0]<=rx_data;
                                if(header_index==3) sequence_id[15:8]<=rx_data;
                                if(header_index==5) begin state<=PAYLOAD; payload_index<=0; end
                            end
                        end
                        PAYLOAD: begin
                            crc<=next_crc;
                            memory_write<=1; memory_address<=payload_index; memory_data<=rx_data;
                            if(payload_index==783) state<=CRC_LOW;
                            else payload_index<=payload_index+1;
                        end
                        CRC_LOW: begin received_crc_low<=rx_data; state<=CRC_HIGH; end
                        CRC_HIGH: begin
                            if({rx_data,received_crc_low}==crc) frame_valid<=1;
                            else rejected<=1;
                            state<=SEARCH_A5;
                        end
                        default: state<=SEARCH_A5;
                    endcase
                end
            end
        end
    end
endmodule
`default_nettype wire

