// Tests the exact helper called by production event.cpp.inc. No fake router.
#include "shared.h"
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <initializer_list>
#define EVENT_PAYLOAD_ONLY15
#include "event.cpp.inc"
static unsigned checks;static void need(bool x,const char* why){checks++;if(!x){fprintf(stderr,"FAIL %s\n",why);exit(1);}}
int main(){uint32_t raw[128];for(unsigned i=0;i<128;i++)raw[i]=0xabc00000+i;for(uint32_t kind: {140u,163u,164u,165u,166u}){Event e={};e.stack_word_count=68;e.stack_words[0]=0x53544e31;need(route_event_payload15(kind,raw,e),"explicit controller diagnostic takes precedence over STN1");need(e.stack_word_count==128&&!memcmp(e.stack_words,raw,512),"all128 raw words survive actual producer router");}
 for(uint32_t kind: {124u,125u}){Event e={};need(route_event_payload15(kind,raw,e)&&e.stack_word_count==80&&!memcmp(e.stack_words,raw,320),"DG11 actual80-word scope preserved");}
 Event empty={};empty.stack_word_count=68;empty.stack_words[0]=0x53544e31;need(!route_event_payload15(3,NULL,empty)&&empty.stack_word_count==68&&empty.stack_words[0]==0x53544e31,"without diagnostic caller retains original stance route");need(sizeof(Event)==1616&&sizeof(Tactical)==13269420,"payload correction leaves wire ABI unchanged");printf("{\"scope\":\"actual_production_event_payload_router\",\"tests\":%u,\"passed\":true,\"game_access\":false,\"sdk_calls\":0}\n",checks);return 0;}
