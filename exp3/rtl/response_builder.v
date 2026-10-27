`timescale 1ns/1ps
`default_nettype none
module response_builder(
    input wire clk, input wire reset, input wire start,
    input wire [15:0] sequence_id, input wire [7:0] status, input wire [7:0] digit,
    input wire [31:0] cycles,
    output reg [7:0] tx_data, output wire tx_valid, input wire tx_ready,
    output reg queued_all
);
    reg active;
    reg [4:0] index;
    reg [15:0] sequence_latched, crc;
    reg [7:0] status_latched, digit_latched;
    reg [31:0] cycles_latched;
    wire [15:0] next_crc;
    assign tx_valid=active;
    crc16_byte update_crc(.crc(crc),.data(tx_data),.next_crc(next_crc));
    always @* begin
        case(index)
            0:tx_data=8'ha5; 1:tx_data=8'h5a;
            2:tx_data=1; 3:tx_data=8'h81;
            4:tx_data=sequence_latched[7:0]; 5:tx_data=sequence_latched[15:8];
            6:tx_data=7; 7:tx_data=0;
            8:tx_data=status_latched; 9:tx_data=digit_latched; 10:tx_data=0;
            11:tx_data=cycles_latched[7:0]; 12:tx_data=cycles_latched[15:8];
            13:tx_data=cycles_latched[23:16]; 14:tx_data=cycles_latched[31:24];
            15:tx_data=crc[7:0]; 16:tx_data=crc[15:8];
            default:tx_data=0;
        endcase
    end
    always @(posedge clk) begin
        if(reset) begin
            active<=0; index<=0; crc<=16'hffff; queued_all<=0;
            sequence_latched<=0; status_latched<=0; digit_latched<=0; cycles_latched<=0;
        end else begin
            queued_all<=0;
            if(start && !active) begin
                active<=1; index<=0; crc<=16'hffff;
                sequence_latched<=sequence_id; status_latched<=status;
                digit_latched<=digit; cycles_latched<=cycles;
            end else if(active && tx_ready) begin
                if(index>=2 && index<=14) crc<=next_crc;
                if(index==16) begin active<=0; queued_all<=1; end
                else index<=index+1;
            end
        end
    end
endmodule
`default_nettype wire

