// TEST ONLY. Ideal functional models, no process variation or race timing.
// Do not add this file to a Gowin hardware project: use vendor primitives there.
`timescale 1ns/1ps
module LUT1(input I0, output F);
 parameter [1:0] INIT=0;
 assign F=INIT[I0];
endmodule
module LUT4(input I0,I1,I2,I3, output F);
 parameter [15:0] INIT=0;
 assign F=INIT[{I3,I2,I1,I0}];
endmodule
module DFFC(input D,CLK,CLEAR, output reg Q);
 parameter INIT=0;
 initial Q=INIT;
 always @(posedge CLK or posedge CLEAR)
  if(CLEAR) Q<=0; else Q<=D;
endmodule
