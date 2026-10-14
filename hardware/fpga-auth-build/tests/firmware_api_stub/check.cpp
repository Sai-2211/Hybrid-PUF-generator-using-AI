#include "Arduino.h"
#include "../../esp32_bridge/esp32_bridge.ino"
#include <cassert>
#include <cstring>
void check(const char *input,const char *expected){
 char buffer[96];std::strcpy(buffer,input);Serial.output.clear();handle_line(buffer);
 assert(Serial.output==expected);
}
int main(){
 Serial1.fpga=true;setup();
 assert(crc8(reinterpret_cast<const uint8_t*>("123456789"),9)==0xF4);
 check("PING","OK PING PUF 64\n");
 check("LOOP 0123456789ABCDEF","OK LOOP EF\n");
 check("READ 0123456789ABCDEF 7","OK READ 0123456789ABCDEF 1111111\n");
 check("READ 0123456789ABCDEE 3","OK READ 0123456789ABCDEE 000\n");
 check("READ 0123456789ABCDEF 2","ERR ARGUMENTS\n");
 check("READ 0123456789ABCDEF 99","ERR ARGUMENTS\n");
 check("READ BAD 7","ERR ARGUMENTS\n");
 check("VERDICT 1","OK VERDICT\n");assert(led==HIGH);
 check("VERDICT 0","OK VERDICT\n");assert(led==LOW);
 disabled=true;
 check("PING","OK PING LINK_ONLY 64\n");
 check("READ 0123456789ABCDEF 7","ERR PUF_DISABLED\n");
 disabled=false;bad_crc=true;
 check("READ 0123456789ABCDEF 7","ERR LINK\n");
 puts("PASS: firmware helpers under desktop API stub: CRC vector, packet parsing, READ, LOOP, arguments, verdict, disabled PUF, corrupt reply.");
}
