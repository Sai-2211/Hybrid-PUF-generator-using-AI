#include <Arduino.h>
#include <ctype.h>
#include <stdlib.h>
#include <string.h>
#if !ARDUINO_USB_CDC_ON_BOOT
#error "Enable Tools > USB CDC On Boot; Serial must use native USB."
#endif
// ESP32-C3 SuperMini: external UART TX=0, RX=1; optional verdict LED=3.
static uint8_t seq_id=0;
static char line[96];
static size_t line_size=0;
static bool discard_line=false;

uint8_t crc8(const uint8_t *data,size_t size) {
 uint8_t crc=0;
 for(size_t i=0;i<size;++i) {
  crc^=data[i];
  for(int b=0;b<8;++b)
   crc=(crc&0x80) ? uint8_t((crc<<1)^0x07) : uint8_t(crc<<1);
 }
 return crc;
}

bool exchange(uint8_t command,uint64_t challenge,uint8_t &status,uint8_t &payload) {
 uint8_t request[13]={0xA5,0x5A,++seq_id,command};
 for(int i=0;i<8;++i) request[4+i]=uint8_t(challenge>>(56-8*i));
 request[12]=crc8(request+2,10);
 while(Serial1.available()) Serial1.read();
 Serial1.write(request,sizeof(request));
 uint8_t reply[6]; size_t have=0;
 unsigned long started=millis();
 while(millis()-started<250) {
  if(!Serial1.available()) { delay(1); continue; }
  uint8_t value=uint8_t(Serial1.read());
  if(have==0 && value!=0x5A) continue;
  if(have==1 && value!=0xA5) { have=(value==0x5A) ? 1 : 0; continue; }
  reply[have++]=value;
  if(have==sizeof(reply)) {
   if(reply[2]!=request[2] || crc8(reply+2,3)!=reply[5]) return false;
   status=reply[3]; payload=reply[4]; return true;
  }
 }
 return false;
}

bool parse_challenge(const char *text,uint64_t &value) {
 if(!text || strlen(text)!=16) return false;
 for(int i=0;i<16;++i) if(!isxdigit((unsigned char)text[i])) return false;
 value=strtoull(text,nullptr,16); return true;
}

void handle_line(char *input) {
 char *save=nullptr;
 char *command=strtok_r(input," \t",&save);
 if(!command) return;
 digitalWrite(3,LOW); // Any new command revokes a previous display.
 uint8_t status=0,payload=0;
 if(strcmp(command,"PING")==0) {
  if(strtok_r(nullptr," \t",&save)) { Serial.println("ERR ARGUMENTS"); return; }
  if(!exchange(0,0,status,payload)) { Serial.println("ERR LINK"); return; }
  if((status!=0 && status!=0x10) || payload!=64) { Serial.println("ERR FPGA_PING"); return; }
  Serial.printf("OK PING %s 64\n",status==0 ? "PUF" : "LINK_ONLY");
 } else if(strcmp(command,"LOOP")==0) {
  uint64_t challenge;
  if(!parse_challenge(strtok_r(nullptr," \t",&save),challenge) ||
     strtok_r(nullptr," \t",&save)) { Serial.println("ERR ARGUMENTS"); return; }
  if(!exchange(2,challenge,status,payload)) { Serial.println("ERR LINK"); return; }
  if(status!=0x20 || payload!=uint8_t(challenge)) { Serial.println("ERR LOOP"); return; }
  Serial.printf("OK LOOP %02X\n",payload);
 } else if(strcmp(command,"READ")==0) {
  uint64_t challenge;
  char *challenge_text=strtok_r(nullptr," \t",&save);
  char *repeat_text=strtok_r(nullptr," \t",&save);
  char *end=nullptr;
  long repeats=repeat_text ? strtol(repeat_text,&end,10) : 0;
  if(!parse_challenge(challenge_text,challenge) || !repeat_text || !*repeat_text ||
     !end || *end || repeats<1 || repeats>31 || !(repeats&1) ||
     strtok_r(nullptr," \t",&save)) { Serial.println("ERR ARGUMENTS"); return; }
  char bits[32];
  for(long i=0;i<repeats;++i) {
   if(!exchange(1,challenge,status,payload)) { Serial.println("ERR LINK"); return; }
   if(status==0xE3) { Serial.println("ERR PUF_DISABLED"); return; }
   if(status!=0 || payload>1) { Serial.println("ERR FPGA_READ"); return; }
   bits[i]=payload ? '1' : '0';
  }
  bits[repeats]=0;
  Serial.printf("OK READ %016llX %s\n",(unsigned long long)challenge,bits);
 } else if(strcmp(command,"VERDICT")==0) {
  char *value=strtok_r(nullptr," \t",&save);
  if(!value || (strcmp(value,"0") && strcmp(value,"1")) ||
     strtok_r(nullptr," \t",&save)) { Serial.println("ERR ARGUMENTS"); return; }
  digitalWrite(3,value[0]=='1' ? HIGH : LOW);
  Serial.println("OK VERDICT");
 } else Serial.println("ERR COMMAND");
}

void setup() {
 pinMode(3,OUTPUT); digitalWrite(3,LOW);
 Serial.begin(115200);
 Serial1.begin(115200,SERIAL_8N1,1,0);
}

void loop() {
 while(Serial.available()) {
  char value=char(Serial.read());
  if(value=='\r') continue;
  if(value=='\n') {
   if(discard_line) Serial.println("ERR LINE_TOO_LONG");
   else { line[line_size]=0; handle_line(line); }
   line_size=0; discard_line=false;
  } else if(!discard_line) {
   if(line_size+1<sizeof(line)) line[line_size++]=value;
   else discard_line=true;
  }
 }
 delay(1);
}
