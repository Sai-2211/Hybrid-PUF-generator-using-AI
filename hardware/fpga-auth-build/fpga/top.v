// First build: ENABLE_PUF=0 gives PING/LOOP only, never fake PUF responses.
// Experimental build: ENABLE_PUF=1 requires implementation and hardware review.
module top #(parameter ENABLE_PUF=0)(input clk,reset_n,uart_rx_pin,
 output uart_tx_pin);
 reg [7:0] power_on=0;
 reg [1:0] reset_sync=0;
 always @(posedge clk) begin
  if(!(&power_on)) power_on<=power_on+1;
  reset_sync<={reset_sync[0],reset_n};
 end
 wire rst=!(&power_on)||!reset_sync[1];
 wire [7:0] rx_byte;
 wire rx_valid,tx_busy;
 reg tx_start=0,core_start=0;
 reg [7:0] tx_byte=0;
 reg [63:0] challenge=0;
 wire core_done,core_response;
 uart_rx rx_unit(clk,rst,uart_rx_pin,rx_byte,rx_valid);
 uart_tx tx_unit(clk,rst,tx_start,tx_byte,uart_tx_pin,tx_busy);
 generate if(ENABLE_PUF) begin: physical
  puf64 core(clk,rst,core_start,challenge,core_done,core_response);
 end else begin: communication_only
  assign core_done=0; assign core_response=0;
 end endgenerate
 function [7:0] crc8;
  input [7:0] previous,value;
  reg [7:0] temp; integer k;
  begin
   temp=previous^value;
   for(k=0;k<8;k=k+1) temp=temp[7] ? (temp<<1)^8'h07 : temp<<1;
   crc8=temp;
  end
 endfunction
 // State 0/1 headers, 2 payload, 3 CRC, 4 PUF wait, 5 reply, 6 TX finish.
 reg [2:0] state=0;
 reg [3:0] index=0;
 reg [7:0] seq_id=0,command=0,request_crc=0;
 reg [7:0] status=0,payload=0,response_crc=0;
 reg [18:0] gap=0;
 always @(posedge clk) begin
  tx_start<=0; core_start<=0;
  if(rst) begin
   state<=0; index<=0; challenge<=0; request_crc<=0; seq_id<=0;
   command<=0; gap<=0; status<=0; payload<=0; response_crc<=0;
  end else begin
   if(state>=1 && state<=3) begin
    if(rx_valid) gap<=0;
    else if(gap==270000) begin state<=0; gap<=0; end
    else gap<=gap+1;
   end else gap<=0;
   case(state)
    0: if(rx_valid && rx_byte==8'hA5) state<=1;
    1: if(rx_valid) begin
     if(rx_byte==8'h5A) begin state<=2; index<=0; request_crc<=0; challenge<=0; end
     else if(rx_byte!=8'hA5) state<=0;
    end
    2: if(rx_valid) begin
     request_crc<=crc8(request_crc,rx_byte);
     if(index==0) seq_id<=rx_byte;
     else if(index==1) command<=rx_byte;
     else challenge<={challenge[55:0],rx_byte};
     if(index==9) state<=3; else index<=index+1;
    end
    3: if(rx_valid) begin
     index<=0;
     if(rx_byte!=request_crc) begin status<=8'hE1; payload<=0; state<=5; end
     else if(command==0) begin
      status<=ENABLE_PUF ? 0 : 8'h10; payload<=8'h40; state<=5;
     end else if(command==2) begin status<=8'h20; payload<=challenge[7:0]; state<=5; end
     else if(command!=1) begin status<=8'hE2; payload<=0; state<=5; end
     else if(!ENABLE_PUF) begin status<=8'hE3; payload<=0; state<=5; end
     else begin core_start<=1; state<=4; end
    end
    4: if(core_done) begin status<=0; payload<={7'b0,core_response}; state<=5; index<=0; end
    5: if(!tx_busy && !tx_start) begin
     tx_start<=1;
     case(index)
      0: begin tx_byte<=8'h5A; response_crc<=crc8(crc8(crc8(0,seq_id),status),payload); end
      1: tx_byte<=8'hA5;
      2: tx_byte<=seq_id;
      3: tx_byte<=status;
      4: tx_byte<=payload;
      5: tx_byte<=response_crc;
     endcase
     if(index==5) state<=6; else index<=index+1;
    end
    6: if(!tx_busy && !tx_start) state<=0;
   endcase
  end
 end
endmodule
