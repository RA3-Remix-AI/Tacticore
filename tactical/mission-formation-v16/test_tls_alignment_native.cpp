// Exact production scalar helpers, including actual TLS and deliberately
// eight-mod-sixteen storage. Never opens a game or calls its SDK.
#define main pending_regression_main
#include "test_pending_native.cpp"
#undef main
static uint32_t tls_cases;static uintptr_t worker_tls;static bool worker_isolated;
static void tls_need(bool yes,const char* text){tls_cases++;if(!yes){fprintf(stderr,"TLS case%u %s\n",tls_cases,text);exit(1);}}
static bool equal_context(const MoveDispatchContext& a,const MoveDispatchContext& b){return a.role==b.role&&a.generation==b.generation&&a.command==b.command&&a.kind==b.kind;}
static DWORD WINAPI tls_worker(void*){worker_tls=(uintptr_t)move_context_words;auto initial=load_move_context();worker_isolated=initial.role==0&&initial.generation==0&&initial.command==0&&initial.kind==0;set_move_context(9,8,7,6);return 0;}
int main(int argc,char** argv){
 alignas(16) BYTE memory[64];memset(memory,0xa5,sizeof(memory));volatile uint32_t* words=(volatile uint32_t*)(memory+8);
 tls_need((uintptr_t)words%16==8&&(uintptr_t)words%4==0,"actual eight-byte displacement");
 clear_dispatch_words(words);MoveDispatchContext zero={};tls_need(equal_context(load_dispatch_words(words),zero),"begin clear on actual unaligned buffer");
 set_dispatch_words(words,1,42,0x12345678,2);MoveDispatchContext first={1,42,0x12345678,2};tls_need(equal_context(load_dispatch_words(words),first),"all scalar fields readable on eight-mod16 buffer");
 MoveDispatchContext prior=load_dispatch_words(words);set_dispatch_words(words,0,99,0xabcdef,1);MoveDispatchContext nested_value={0,99,0xabcdef,1};tls_need(equal_context(load_dispatch_words(words),nested_value),"nested begin stores distinct context");
 store_dispatch_words(words,prior);tls_need(equal_context(load_dispatch_words(words),first),"prior restore on eight-mod16 buffer");
 clear_dispatch_words(words);tls_need(equal_context(load_dispatch_words(words),zero),"final clear on eight-mod16 buffer");
 bool guard=true;for(unsigned i=0;i<sizeof(memory);i++)if((i<8||i>=24)&&memory[i]!=0xa5)guard=false;tls_need(guard,"all scalar stores stay within exact sixteen bytes");
 clear_move_context();tls_need(equal_context(load_move_context(),zero),"real TLS begin clear");set_move_context(1,42,0x12345678,2);auto saved=load_move_context();set_move_context(0,99,0xabcdef,1);tls_need(equal_context(load_move_context(),nested_value),"real TLS nested begin");restore_move_context(saved);tls_need(equal_context(load_move_context(),first),"real TLS prior restoration");
 HANDLE child=CreateThread(NULL,0,tls_worker,NULL,0,NULL);tls_need(child!=NULL,"actual second OS thread created");tls_need(WaitForSingleObject(child,5000)==WAIT_OBJECT_0,"actual second thread completed");CloseHandle(child);
 tls_need(worker_tls!=(uintptr_t)move_context_words&&worker_isolated,"actual TLS isolated across threads, no global replacement");tls_need(equal_context(load_move_context(),first),"other thread cannot change caller prior context");clear_move_context();tls_need(equal_context(load_move_context(),zero),"final real TLS clear");
 if(argc>1){FILE* out=fopen(argv[1],"wb");if(!out)return 2;fprintf(out,"{\"protocol\":\"actual_cpp_tls_scalar_alignment_regression_v1\",\"cases\":%u,\"passed\":true,\"buffer_address\":%u,\"buffer_mod16\":%u,\"buffer_mod4\":%u,\"context_bytes\":%u,\"main_tls_address\":%u,\"worker_tls_address\":%u,\"actual_thread_isolation\":true,\"begin_and_restore\":true,\"game_access\":false,\"sdk_calls\":0,\"capability_granted\":false}",tls_cases,(unsigned)(uintptr_t)words,(unsigned)((uintptr_t)words%16),(unsigned)((uintptr_t)words%4),(unsigned)sizeof(MoveDispatchContext),(unsigned)(uintptr_t)move_context_words,(unsigned)worker_tls);fclose(out);}
 printf("{\"tls_alignment_cases\":%u,\"buffer_mod16\":8,\"sdk_calls\":0,\"game_access\":false}\n",tls_cases);return 0;
}
