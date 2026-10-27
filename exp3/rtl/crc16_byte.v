`timescale 1ns/1ps
`default_nettype none
module crc16_byte(input wire [15:0] crc, input wire [7:0] data, output reg [15:0] next_crc);
    integer bit_index;
    always @* begin
        next_crc = crc ^ {data, 8'h00};
        for(bit_index=0; bit_index<8; bit_index=bit_index+1)
            if(next_crc[15]) next_crc=(next_crc<<1)^16'h1021;
            else next_crc=next_crc<<1;
    end
endmodule
`default_nettype wire

