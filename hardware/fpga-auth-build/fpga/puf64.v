// EXPERIMENTAL: balanced placement, LUT mapping and routing are not supplied.
// Check final netlist: 128 stage LUT4s + 2 launch LUT1s + 1 DFFC must survive.
module puf64(input clk,rst,start,input [63:0] challenge,
 output reg done=0,output reg response=0);
 (* syn_keep=1, keep=1 *) wire [64:0] upper,lower;
 (* syn_preserve=1 *) reg [63:0] challenge_reg=0;
 (* syn_preserve=1 *) reg launch=0;
 reg clear_arbiter=1;
 (* syn_keep=1, keep=1 *) wire arbiter_q;
 LUT1 upper_launch(.I0(launch),.F(upper[0]));
 defparam upper_launch.INIT=2'b10;
 LUT1 lower_launch(.I0(launch),.F(lower[0]));
 defparam lower_launch.INIT=2'b10;
 genvar i;
 generate for(i=0;i<64;i=i+1) begin: stage
  LUT4 mux_upper(.I0(upper[i]),.I1(lower[i]),
   .I2(challenge_reg[i]),.I3(1'b0),.F(upper[i+1]));
  defparam mux_upper.INIT=16'hCACA;
  LUT4 mux_lower(.I0(upper[i]),.I1(lower[i]),
   .I2(challenge_reg[i]),.I3(1'b0),.F(lower[i+1]));
  defparam mux_lower.INIT=16'hACAC;
 end endgenerate
 // DFFC provides asynchronous clear. DFFR is synchronous reset, not equivalent.
 // Review the intentional fabric/local clock route into the arbiter in Gowin.
 DFFC arbiter(.D(upper[64]),.CLK(lower[64]),.CLEAR(clear_arbiter),.Q(arbiter_q));
 defparam arbiter.INIT=1'b0;
 (* syn_preserve=1 *) reg q_meta=0,q_sync=0;
 reg [1:0] state=0;
 reg [7:0] count=0;
 always @(posedge clk) begin
  q_meta<=arbiter_q; q_sync<=q_meta; done<=0;
  if(rst) begin
   state<=0; launch<=0; clear_arbiter<=1; response<=0;
   challenge_reg<=0; count<=0; q_meta<=0; q_sync<=0;
  end else case(state)
   0: if(start) begin
    challenge_reg<=challenge; launch<=0; clear_arbiter<=1;
    count<=255; state<=1;
   end
   1: if(count!=0) count<=count-1;
      else begin clear_arbiter<=0; count<=255; state<=2; end
   2: if(count!=0) count<=count-1;
      else begin launch<=1; count<=255; state<=3; end
   3: if(count!=0) count<=count-1;
      else begin
       response<=q_sync; done<=1; launch<=0; clear_arbiter<=1; state<=0;
      end
  endcase
 end
endmodule
