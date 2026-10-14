#pragma once
#include <cstdint>
#include <cstddef>
#include <cstdio>
#include <cstdarg>
#include <deque>
#include <string>
#define ARDUINO_USB_CDC_ON_BOOT 1
#define LOW 0
#define HIGH 1
#define OUTPUT 1
#define SERIAL_8N1 0
inline unsigned long clock_ms=0;
inline bool bad_crc=false,disabled=false;
inline int led=0;
inline unsigned long millis(){return clock_ms++;}
inline void delay(unsigned long n){clock_ms+=n;}
inline void pinMode(int,int){}
inline void digitalWrite(int pin,int value){if(pin==3)led=value;}
inline uint8_t stub_crc(const uint8_t *p,size_t n){
 uint8_t crc=0;
 for(size_t i=0;i<n;i++){crc^=p[i];for(int b=0;b<8;b++)crc=(crc&128)?uint8_t((crc<<1)^7):uint8_t(crc<<1);}
 return crc;
}
struct FakeSerial {
 bool fpga=false;
 std::deque<uint8_t> input;
 std::string output;
 void begin(unsigned long,int=0,int=-1,int=-1){}
 int available(){return int(input.size());}
 int read(){if(input.empty())return -1;auto v=input.front();input.pop_front();return v;}
 size_t write(const uint8_t *p,size_t n){
  if(!fpga)return n;
  if(n!=13||p[0]!=0xA5||p[1]!=0x5A||stub_crc(p+2,10)!=p[12])return n;
  uint8_t status=0,payload=0;
  if(p[3]==0){status=disabled?0x10:0;payload=64;}
  else if(p[3]==1){status=disabled?0xE3:0;payload=p[11]&1;}
  else if(p[3]==2){status=0x20;payload=p[11];}
  else status=0xE2;
  uint8_t reply[6]={0x5A,0xA5,p[2],status,payload,0};
  reply[5]=stub_crc(reply+2,3);if(bad_crc)reply[5]^=1;
  for(auto value:reply)input.push_back(value);
  return n;
 }
 void println(const char *text){output+=text;output+='\n';}
 void printf(const char *fmt,...){
  char buffer[256];va_list args;va_start(args,fmt);vsnprintf(buffer,sizeof(buffer),fmt,args);va_end(args);output+=buffer;
 }
};
inline FakeSerial Serial,Serial1;
