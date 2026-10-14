// Serial-wire integration test. No silicon identity is simulated here.
`timescale 1ns/1ps
module tb_protocol;
 localparam DIV=234;
 reg clk=0,reset_n=0,rx=1;
 always #5 clk=~clk; // Only clock counts matter to these UART tests.
 wire tx0,tx1;
 top #(.ENABLE_PUF(0)) link_only(clk,reset_n,rx,tx0);
 top #(.ENABLE_PUF(1)) functional_core(clk,reset_n,rx,tx1);
 reg [7:0] received0[0:127],received1[0:127];
 integer n0=0,n1=0;
 reg [7:0] byte0,byte1;
 integer k0,k1;
 // Independent UART decoders, sampled at the middle of each bit.
 initial forever begin
  @(negedge tx0);
  repeat(DIV/2) @(posedge clk);
  if(tx0!==0) $fatal(1,"TX0 start bit");
  for(k0=0;k0<8;k0=k0+1) begin
   repeat(DIV) @(posedge clk); byte0[k0]=tx0;
  end
  repeat(DIV) @(posedge clk);
  if(tx0!==1) $fatal(1,"TX0 stop bit");
  received0[n0]=byte0; n0=n0+1;
 end
 initial forever begin
  @(negedge tx1);
  repeat(DIV/2) @(posedge clk);
  if(tx1!==0) $fatal(1,"TX1 start bit");
  for(k1=0;k1<8;k1=k1+1) begin
   repeat(DIV) @(posedge clk); byte1[k1]=tx1;
  end
  repeat(DIV) @(posedge clk);
  if(tx1!==1) $fatal(1,"TX1 stop bit");
  received1[n1]=byte1; n1=n1+1;
 end
 function [7:0] crc8;
  input [7:0] previous,value;
  reg [7:0] temp; integer j;
  begin
   temp=previous^value;
   for(j=0;j<8;j=j+1) temp=temp[7]?(temp<<1)^8'h07:temp<<1;
   crc8=temp;
  end
 endfunction
 task send_byte;
  input [7:0] value; integer j;
  begin
   @(negedge clk); rx=0; repeat(DIV) @(negedge clk);
   for(j=0;j<8;j=j+1) begin rx=value[j]; repeat(DIV) @(negedge clk); end
   rx=1; repeat(DIV) @(negedge clk);
  end
 endtask
 task send_packet;
  input [7:0] seq_id,command;
  input [63:0] challenge;
  input corrupt;
  reg [7:0] sum,value; integer j;
  begin
   send_byte(8'hA5); send_byte(8'h5A);
   send_byte(seq_id); send_byte(command);
   sum=crc8(crc8(0,seq_id),command);
   for(j=7;j>=0;j=j-1) begin
    value=(challenge>>(8*j)); send_byte(value); sum=crc8(sum,value);
   end
   send_byte(corrupt ? sum^8'h01 : sum);
  end
 endtask
 task check_reply;
  input integer offset;
  input [7:0] seq_id,status0,status1,payload;
  input any_bit;
  integer timeout; reg [7:0] sum0,sum1;
  begin
   timeout=0;
   while((n0<offset+6 || n1<offset+6) && timeout<50000) begin
    @(posedge clk); timeout=timeout+1;
   end
   if(n0!=offset+6 || n1!=offset+6) $fatal(1,"Missing/extra serial reply");
   if(received0[offset]!==8'h5A || received1[offset]!==8'h5A ||
      received0[offset+1]!==8'hA5 || received1[offset+1]!==8'hA5)
    $fatal(1,"Reply header");
   if(received0[offset+2]!==seq_id || received1[offset+2]!==seq_id)
    $fatal(1,"Sequence mismatch");
   if(received0[offset+3]!==status0 || received1[offset+3]!==status1)
    $fatal(1,"Status mismatch");
   if(received0[offset+4]!==payload) $fatal(1,"Link-only payload mismatch");
   if(any_bit) begin
    if(received1[offset+4]!==0 && received1[offset+4]!==1)
     $fatal(1,"Undefined functional core result");
   end else if(received1[offset+4]!==payload) $fatal(1,"Core payload mismatch");
   sum0=crc8(crc8(crc8(0,seq_id),status0),received0[offset+4]);
   sum1=crc8(crc8(crc8(0,seq_id),status1),received1[offset+4]);
   if(received0[offset+5]!==sum0 || received1[offset+5]!==sum1)
    $fatal(1,"Reply CRC mismatch");
   // Finish the stop bit and allow top-level FSM to return to idle.
   repeat(DIV*2) @(posedge clk);
  end
 endtask
 reg [3:0] lut_inputs=0;
 wire upper,lower;
 LUT4 #(.INIT(16'hCACA)) u(lut_inputs[0],lut_inputs[1],lut_inputs[2],lut_inputs[3],upper);
 LUT4 #(.INIT(16'hACAC)) l(lut_inputs[0],lut_inputs[1],lut_inputs[2],lut_inputs[3],lower);
 integer j;
 reg [7:0] crc_vector;
 initial begin
  for(j=0;j<16;j=j+1) begin
   lut_inputs=j; #1;
   if(upper!==(lut_inputs[2]?lut_inputs[1]:lut_inputs[0]) ||
      lower!==(lut_inputs[2]?lut_inputs[0]:lut_inputs[1]))
    $fatal(1,"Straight/cross LUT truth table");
  end
  crc_vector=0;
  for(j=1;j<=9;j=j+1) crc_vector=crc8(crc_vector,8'h30+j);
  if(crc_vector!==8'hF4) $fatal(1,"Independent CRC check vector");
  repeat(300) @(negedge clk); reset_n=1;
  repeat(300) @(negedge clk);
  send_packet(8'h11,0,0,0); check_reply(0,8'h11,8'h10,0,8'h40,0);
  send_packet(8'h12,2,64'h0123456789ABCDEF,0); check_reply(6,8'h12,8'h20,8'h20,8'hEF,0);
  send_packet(8'h13,1,64'h0123456789ABCDEF,0); check_reply(12,8'h13,8'hE3,0,0,1);
  if(functional_core.challenge!==64'h0123456789ABCDEF) $fatal(1,"Challenge byte order");
  send_packet(8'h14,0,0,1); check_reply(18,8'h14,8'hE1,8'hE1,0,0);
  send_packet(8'h15,8'h99,0,0); check_reply(24,8'h15,8'hE2,8'hE2,0,0);
  // An incomplete packet must expire, allowing a complete subsequent request.
  send_byte(8'hA5); send_byte(8'h5A); send_byte(8'h16);
  repeat(271000) @(negedge clk);
  send_packet(8'h17,2,64'hFEDCBA9876543210,0); check_reply(30,8'h17,8'h20,8'h20,8'h10,0);
  // Reset interrupts a partial packet without leaving the parser stuck.
  send_byte(8'hA5); send_byte(8'h5A); send_byte(8'h18);
  reset_n=0; repeat(20) @(negedge clk); reset_n=1;
  repeat(20) @(negedge clk);
  send_packet(8'h19,0,0,0); check_reply(36,8'h19,8'h10,0,8'h40,0);
  send_packet(8'h1A,1,64'hFFFFFFFFFFFFFFFF,0); check_reply(42,8'h1A,8'hE3,0,0,1);
  if(functional_core.physical.core.challenge_reg!==64'hFFFFFFFFFFFFFFFF)
   $fatal(1,"Later challenge was not latched into the physical core");
  send_packet(8'h1B,1,0,0); check_reply(48,8'h1B,8'hE3,0,0,1);
  if(functional_core.physical.core.challenge_reg!==0)
   $fatal(1,"Repeated evaluation did not accept a new challenge");
  $display("PASS: LUT truth tables; UART wire frames; PING; LOOP; evaluation control; disabled PUF; byte order; CRC; bad command; packet timeout; reset");
  $finish;
 end
 initial begin #20000000; $fatal(1,"Global test timeout"); end
endmodule
