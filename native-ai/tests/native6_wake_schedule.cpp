// Offline only. Compile with the reviewed x86 toolchain and -I pointing at
// a generated Native6 profile directory. Fake posting never opens a Game.
#include "../strategic-portable-runtime-v6/native.cpp"
#include <assert.h>
static unsigned posted;static LPARAM last_ticket;
static BOOL WINAPI accept(DWORD,UINT,WPARAM,LPARAM ticket){++posted;last_ticket=ticket;return TRUE;}
static BOOL WINAPI reject(DWORD,UINT,WPARAM,LPARAM){++posted;return FALSE;}
int main(){
 assert(wake_bootstrap==1);assert(queue_wake(accept));LPARAM first=last_ticket;
 for(unsigned i=0;i<1000;i++)assert(queue_wake(accept));assert(posted==1);
 assert(!claim_wake(0));assert(!claim_wake(first+1));finish_wake(first);assert(wake_pending==first);
 assert(claim_wake(first));assert(!claim_wake(first));
 for(unsigned i=0;i<1000;i++)assert(queue_wake(accept));assert(posted==1);
 finish_wake(0);finish_wake(first+1);assert(wake_pending==-first);
 finish_wake(first);assert(wake_pending==0);assert(queue_wake(accept));LPARAM second=last_ticket;
 assert(second!=first);assert(!claim_wake(first));finish_wake(first);assert(wake_pending==second);
 assert(claim_wake(second));assert(!claim_wake(second));finish_wake(second);
 assert(!queue_wake(reject));assert(wake_pending==0);assert(queue_wake(accept));
 assert(claim_wake(last_ticket));finish_wake(last_ticket);
 InterlockedExchange(&wake_serial,0x3fffffff);assert(!queue_wake(accept));assert(wake_pending==0);
 printf("{\"passed\":true,\"checks\":[\"coalesced_queued\",\"coalesced_active\",\"wrong_ticket\",\"unclaimed_finish\",\"nested_duplicate\",\"old_duplicate_after_new\",\"failed_post_retry\",\"ticket_exhaustion\"],\"game_starts\":0,\"game_memory_reads\":0,\"native_commands\":0}\n");
 return 0;
}
