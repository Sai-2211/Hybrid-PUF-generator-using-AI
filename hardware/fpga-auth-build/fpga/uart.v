// 27 MHz, 115200 baud, 8N1. DIV=234 gives 0.16% baud error.
module uart_rx #(parameter DIV=234)(input clk,rst,rx,
 output reg [7:0] data, output reg valid);
 reg [1:0] sync=3, state=0;
 reg [15:0] count=0;
 reg [2:0] index=0;
 reg [7:0] bits=0;
 always @(posedge clk) begin
  sync<={sync[0],rx}; valid<=0;
  if(rst) begin state<=0; count<=0; data<=0; end
  else case(state)
   0: if(!sync[1]) begin count<=DIV/2-1; state<=1; end
   1: if(count!=0) count<=count-1;
      else if(!sync[1]) begin count<=DIV-1; index<=0; state<=2; end
      else state<=0;
   2: if(count!=0) count<=count-1;
      else begin
       bits[index]<=sync[1]; count<=DIV-1;
       if(index==7) state<=3; else index<=index+1;
      end
   3: if(count!=0) count<=count-1;
      else begin
       if(sync[1]) begin data<=bits; valid<=1; end
       state<=0;
      end
  endcase
 end
endmodule

module uart_tx #(parameter DIV=234)(input clk,rst,start,
 input [7:0] data, output tx, output reg busy=0);
 reg [9:0] bits=10'h3ff;
 reg [15:0] count=0;
 reg [3:0] index=0;
 assign tx=busy ? bits[0] : 1'b1;
 always @(posedge clk) begin
  if(rst) begin busy<=0; bits<=10'h3ff; count<=0; end
  else if(!busy) begin
   if(start) begin
    bits<={1'b1,data,1'b0}; busy<=1; count<=DIV-1; index<=0;
   end
  end else if(count!=0) count<=count-1;
  else if(index==9) busy<=0;
  else begin bits<={1'b1,bits[9:1]}; index<=index+1; count<=DIV-1; end
 end
endmodule
