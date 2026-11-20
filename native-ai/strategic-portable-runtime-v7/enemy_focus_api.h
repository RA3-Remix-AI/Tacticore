#pragma once

#include "strategic_enemy_focus_lease_v1.h"
namespace focus = ra3_enemy_focus_v1;

static bool focus_signatures() {
 return flag_bytes(0x8bdb50,"\x83\xec\x10\x56\x8b\xf1\x66\x83\x7e\x30\x00\x77\x50",13)&&
        flag_bytes(0x8bdbc0,"\x32\xc0\x88\x41\x24\x88\x41\x25\x8b\x44\x24\x04\x89\x41\x20\xe8\xbc\xfa\xff\xff\xc2\x04\x00",23);
}

// Native relationship of `player` towards player id `other` (0 enemies, 1 neutral, 2 allies).
// A bounded hash-bucket walk that is re-read for consistency; absent or changing entries fail.
static bool relation_of(uint32_t player,uint32_t other,uint32_t& value) {
 const uint32_t container=word(player+0xfc);
 uint32_t metadata[3]={},metadata_again[3]={};
 if(!container||!read(container+8,metadata,sizeof(metadata))||!metadata[0]||
    metadata[1]<1||metadata[1]>4096||!metadata[2])return false;
 const uint32_t bucket=metadata[0]+(other%metadata[1])*4;
 uint32_t node=0,first=0;
 if(!read(bucket,&node,4))return false;
 first=node;
 uint32_t addresses[100]={},rows[100][3]={};unsigned count=0;bool found=false;
 while(node) {
  if(count==100||node%4)return false;
  for(unsigned i=0;i<count;i++)if(addresses[i]==node)return false;
  addresses[count]=node;
  if(!read(node,rows[count],sizeof(rows[count])))return false;
  if(rows[count][0]==other){found=true;value=rows[count][1];++count;break;}
  node=rows[count][2];++count;
 }
 uint32_t current=0;
 if(!found||word(player+0xfc)!=container||!read(container+8,metadata_again,sizeof(metadata_again))||
    memcmp(metadata,metadata_again,sizeof(metadata))||!read(bucket,&current,4)||current!=first)return false;
 for(unsigned i=0;i<count;i++) {
  uint32_t again[3]={};
  if(!read(addresses[i],again,sizeof(again))||memcmp(rows[i],again,sizeof(again)))return false;
 }
 return true;
}

static bool same_focus_selection(const focus::Snapshot& a,const focus::Snapshot& b) {
 if(a.manual!=b.manual||a.isolated!=b.isolated||a.enemy_mask!=b.enemy_mask||a.alive_mask!=b.alive_mask)return false;
 for(uint32_t i=0;i<focus::MAX_PLAYERS;i++)if(a.priority[i]!=b.priority[i])return false;
 return true;
}

class FocusEnvironment final : public focus::Environment {
public:
 // One consistent read of the own enemy selector and the participants. Any number of
 // enemies and allies (human or AI) with ids 0..15; every other player must be a mutual
 // enemy or a mutual ally of the own player, anything else (neutral, one-sided) fails.
 bool sample(focus::Snapshot& value) override {
  if(!guard(NULL,binding)||!focus_signatures())return false;
  const uint64_t started_ms=GetTickCount64();
  const uint32_t first_frame=word(binding.game+0x50);
  const uint32_t own=word(binding.owner+0x20);
  if(own>=focus::MAX_PLAYERS)return false;
  const uint32_t tactical=word(binding.ai+0x6f8),selector=word(tactical+0x34);
  BYTE header[0x32]={},again[0x32]={};
  if(!tactical||!selector||!read(selector,header,sizeof(header)))return false;
  uint32_t owner=0,begin=0,end=0,scheme=0;
  memcpy(&owner,header+4,4);memcpy(&begin,header+8,4);memcpy(&end,header+12,4);memcpy(&scheme,header+0x20,4);
  if(owner!=binding.owner||scheme!=2||header[0x24]>1||header[0x25]>1||end<begin||
     end-begin>8*focus::MAX_PLAYERS||(end-begin)%8||bool(begin)!=bool(end))return false;
  uint32_t entries[2*focus::MAX_PLAYERS]={},entries_again[2*focus::MAX_PLAYERS]={};
  if(end>begin&&!read(begin,entries,end-begin))return false;
  value={};value.selector=selector;value.automatic_scheme=scheme;
  value.manual=header[0x24];value.isolated=header[0x25];value.own_player=own;
  uint16_t lock=0;memcpy(&lock,header+0x30,2);value.enumeration_lock=lock;
  const uint32_t manager=word(0xcdd1a0);
  if(word(manager)!=0xc07ab8)return false;
  uint32_t players[20]={},players_again[20]={};BYTE defeated[20]={},defeated_again[20]={};
  if(!read(manager+0x48,players,sizeof(players))||!read(manager+0xa0,defeated,sizeof(defeated)))return false;
  const uint32_t player_list=word(0xce8c9c);
  if(!player_list)return false;
  uint32_t present=0,combatants[focus::MAX_PLAYERS]={};
  for(unsigned i=0;i<20;i++) {
   if(!players[i])continue;
   const uint32_t player=word(players[i]+0x20);
   if(word(players[i])!=0xc5bce0||player>=focus::MAX_PLAYERS||(present&(1u<<player))||defeated[i]>1)return false;
   if(word(player_list+0x30+4*player)!=players[i])return false;
   if(player==own&&players[i]!=binding.owner)return false;
   present|=1u<<player;combatants[player]=players[i];
   if(!defeated[i])value.alive_mask|=1u<<player;
  }
  if(!(present&(1u<<own)))return false;
  for(uint32_t q=0;q<focus::MAX_PLAYERS;q++) {
   if(q==own||!(present&(1u<<q)))continue;
   uint32_t toward=0,back=0;
   if(!relation_of(binding.owner,q,toward)||!relation_of(combatants[q],own,back))return false;
   if(toward==0&&back==0)value.enemy_mask|=1u<<q;
   else if(toward!=2||back!=2)return false;
  }
  uint32_t seen=0;
  for(unsigned i=0;i<(end-begin)/8;i++) {
   const uint32_t priority=entries[2*i],player=entries[2*i+1];
   if(player>=focus::MAX_PLAYERS||(seen&(1u<<player))||!(value.enemy_mask&(1u<<player))||
      priority<1||priority>10)return false;
   seen|=1u<<player;value.priority[player]=priority;
  }
  value.paused=word(binding.game+0x15c)!=0;
  if(!read(selector,again,sizeof(again))||memcmp(header,again,sizeof(header))||
     (end>begin&&(!read(begin,entries_again,end-begin)||memcmp(entries,entries_again,end-begin)))||
     !read(manager+0x48,players_again,sizeof(players_again))||memcmp(players,players_again,sizeof(players))||
     !read(manager+0xa0,defeated_again,sizeof(defeated_again))||memcmp(defeated,defeated_again,sizeof(defeated))||
     word(0xcdd1a0)!=manager||word(0xce8c9c)!=player_list||word(binding.owner+0x20)!=own||
     word(binding.ai+0x6f8)!=tactical||word(tactical+0x34)!=selector)return false;
  for(uint32_t q=0;q<focus::MAX_PLAYERS;q++)
   if((present&(1u<<q))&&word(player_list+0x30+4*q)!=combatants[q])return false;
  if(!guard(NULL,binding))return false;
  const uint32_t last_frame=word(binding.game+0x50);
  const uint64_t ended_ms=GetTickCount64();
  if(!first_frame||last_frame<first_frame||last_frame-first_frame>2||ended_ms<started_ms||ended_ms-started_ms>250)
   return false;
  value.frame=last_frame;value.callback=callback_serial;value.ms=ended_ms;value.binding_matches=true;
  last_sample_=value;has_sample_=true;
  return true;
 }

 bool persist(const focus::Audit& value) override {
  if(!journal||!p||audit_sequence>=4096)return false;
  pending_phase_=value.phase;deadline_frame_=value.deadline_frame;deadline_ms_=value.deadline_ms;
  FocusStatus status={};status.phase=(uint32_t)value.phase;status.baseline_captured=1;
  status.selector=value.selector;status.baseline_scheme=value.baseline_scheme;status.target_player=value.target_player;
  status.request=value.request;status.manual=value.observed.manual;status.isolated=value.observed.isolated;
  status.own_player=value.observed.own_player;status.enemy_mask=value.observed.enemy_mask;
  status.alive_mask=value.observed.alive_mask;
  for(uint32_t i=0;i<focus::MAX_PLAYERS;i++)status.priority[i]=value.observed.priority[i];
  status.frame=value.observed.frame;status.callback=value.observed.callback;status.deadline_frame=value.deadline_frame;
  status.call_reservations=value.call_reservations;status.reserved=0;
  status.ms=value.observed.ms;status.deadline_ms=value.deadline_ms;
  p->focus=status;
  JournalRecord row={};row.magic=MAGIC;row.version=7;row.sequence=++audit_sequence;row.size=sizeof(row);row.kind=3;
  row.callback_serial=callback_serial;row.intent_not_after_frame=value.deadline_frame;row.binding=sealed;
  row.focus=status;row.end=0x454e4437;
  DWORD written=0;
  if(!WriteFile(journal,&row,sizeof(row),&written,NULL)||written!=sizeof(row)||!FlushFileBuffers(journal))return false;
  p->journal_records=audit_sequence;return true;
 }

 bool set_priority(uint32_t selector,uint32_t player,uint32_t priority) override {
  if(player>=focus::MAX_PLAYERS||priority!=10||!has_sample_||
     !(focus::focusable(last_sample_)&(1u<<player))||!call_guard(selector,false))return false;
  using SetPriority=void (__attribute__((thiscall))*)(void*,uint32_t,uint32_t);
  ((SetPriority)0x8bdb50)((void*)(uintptr_t)selector,player,priority);
  return true;
 }

 bool restore_automatic(uint32_t selector,uint32_t scheme) override {
  if(scheme!=2||!call_guard(selector,pending_phase_==focus::Phase::RestoreUnknown))return false;
  using AutomaticScheme=void (__attribute__((thiscall))*)(void*,uint32_t);
  ((AutomaticScheme)0x8bdbc0)((void*)(uintptr_t)selector,scheme);
  return true;
 }

private:
 focus::Phase pending_phase_=focus::Phase::Empty;
 uint32_t deadline_frame_=0;
 uint64_t deadline_ms_=0;
 focus::Snapshot last_sample_={};
 bool has_sample_=false;
 bool call_guard(uint32_t selector,bool restoring) {
  if(!has_sample_)return false;
  const focus::Snapshot expected=last_sample_;
  focus::Snapshot value={};
  return sample(value)&&value.selector==selector&&!value.enumeration_lock&&same_focus_selection(value,expected)&&
   (restoring||(!value.paused&&value.frame<deadline_frame_&&value.ms<deadline_ms_));
 }
};

static FocusEnvironment* focus_environment;
static focus::Lease* focus_lease;
