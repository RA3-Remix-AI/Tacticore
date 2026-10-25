// Pure ReadProcessMemory diagnostics. Never installs hooks or sends commands.
#include "shared.h"
#include "native_layout_rvas.h"
#include <tlhelp32.h>
#include <wincrypt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>
static bool valid_executable(DWORD pid){
 HANDLE p=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,pid);char path[32768];DWORD size=sizeof(path);
 if(!p||!QueryFullProcessImageNameA(p,0,path,&size)){if(p)CloseHandle(p);return false;}CloseHandle(p);
 const char* base=strrchr(path,'\\');if(!base||_stricmp(base+1,"ra3_1.12.game"))return false;
 HANDLE file=CreateFileA(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);if(file==INVALID_HANDLE_VALUE)return false;
 HCRYPTPROV provider=0;HCRYPTHASH hash=0;bool okay=false;
 if(CryptAcquireContextA(&provider,NULL,NULL,PROV_RSA_AES,CRYPT_VERIFYCONTEXT)&&CryptCreateHash(provider,CALG_SHA_256,0,0,&hash)){
  BYTE data[65536];DWORD read=0;BOOL result;
  while((result=ReadFile(file,data,sizeof(data),&read,NULL))&&read)if(!CryptHashData(hash,data,read,0)){result=FALSE;break;}
  BYTE digest[32];DWORD n=sizeof(digest);char hex[65]={};
  if(result&&CryptGetHashParam(hash,HP_HASHVAL,digest,&n,0)){for(int i=0;i<32;i++)sprintf(hex+i*2,"%02x",digest[i]);okay=!strcmp(hex,"ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165");}
 }
 if(hash)CryptDestroyHash(hash);
 if(provider)CryptReleaseContext(provider,0);
 CloseHandle(file);return okay;
}
static bool file_hash(const char* path,char out[65]){HANDLE f=CreateFileA(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,0,NULL);if(f==INVALID_HANDLE_VALUE)return false;HCRYPTPROV provider=0;HCRYPTHASH hash=0;bool okay=false;if(CryptAcquireContextA(&provider,NULL,NULL,PROV_RSA_AES,CRYPT_VERIFYCONTEXT)&&CryptCreateHash(provider,CALG_SHA_256,0,0,&hash)){BYTE data[65536],digest[32];DWORD n=0;BOOL r;while((r=ReadFile(f,data,sizeof(data),&n,NULL))&&n)if(!CryptHashData(hash,data,n,0)){r=FALSE;break;}n=32;if(r&&CryptGetHashParam(hash,HP_HASHVAL,digest,&n,0)){for(int i=0;i<32;i++)sprintf(out+i*2,"%02x",digest[i]);okay=true;}}if(hash)CryptDestroyHash(hash);if(provider)CryptReleaseContext(provider,0);CloseHandle(f);return okay;}
static bool rpm(HANDLE p,uint32_t a,void* out,SIZE_T size){SIZE_T got=0;return ReadProcessMemory(p,(void*)(uintptr_t)a,out,size,&got)&&got==size;}
static void words(const uint32_t a[4]){printf("[%u,%u,%u,%u]",a[0],a[1],a[2],a[3]);}
int main(int argc,char**argv){
 if(argc!=2)return 2;DWORD pid=strtoul(argv[1],NULL,0);if(!valid_executable(pid))return 3;
 HANDLE modules=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,pid);if(modules==INVALID_HANDLE_VALUE)return 4;MODULEENTRY32 me={};me.dwSize=sizeof(me);uint32_t base=0;char path[MAX_PATH]={};
 if(Module32First(modules,&me))do{if(!_stricmp(me.szModule,"TacticalMissionFormation15.dll")){base=(uintptr_t)me.modBaseAddr;strncpy(path,me.szExePath,sizeof(path)-1);break;}}while(Module32Next(modules,&me));CloseHandle(modules);char digest[65]={};if(!base||!file_hash(path,digest)||strcmp(digest,NATIVE_DLL_SHA))return 5;
 HANDLE process=OpenProcess(PROCESS_VM_READ|PROCESS_QUERY_LIMITED_INFORMATION,FALSE,pid);if(!process)return 6;uint32_t pointer=0,timer=1;Tactical* s=new Tactical();
 if(!rpm(process,base+NATIVE_P_RVA,&pointer,4)||!rpm(process,base+NATIVE_TIMER_RVA,&timer,4)||!pointer||!rpm(process,pointer,s,offsetof(Tactical,events))||s->magic!=T_MAGIC||s->version!=15||s->pid!=pid){CloseHandle(process);delete s;return 7;}
 printf("{\"protocol\":\"mfm11_native_readonly_snapshot_v1\",\"mutations\":false,\"sdk_calls\":0,\"pid\":%u,\"module_base\":\"0x%x\",\"shared_pointer\":\"0x%x\",\"native_binary_sha256\":\"%s\",\"timer\":%u,\"phase\":%ld,\"error\":%u,\"restore_mask\":%u,\"active\":%ld,\"issued_frame\":%u,\"returned_frame\":%u,\"seq\":%u,\"token\":%u,\"session_words\":",(unsigned)pid,base,pointer,digest,timer,s->phase,s->error,s->restore_mask,s->active,s->issued_frame,s->returned_frame,s->seq,s->token);words(s->session);printf(",\"commander_words\":");words(s->commander);printf(",\"command_words\":");words(s->command);printf(",\"task_words\":");words(s->task);
 printf(",\"front_id\":%u,\"support_id\":%u,\"owner\":\"0x%x\",\"logic\":\"0x%x\",\"mission_stage\":%u,\"motion_state\":%u,\"front_return_verified\":%u,\"support_return_verified\":%u,\"regroup_count\":%u,\"leader_move_count\":%u,\"follow_move_count\":%u,\"crumb_counts\":[%u,%u],\"entries\":[",s->object_id,s->support.id,s->owner,s->logic,s->mission_stage,s->motion_state,s->return_verified,s->support.returned,s->regroup_count,s->leader_move_count,s->follow_move_count,s->crumb_count[0],s->crumb_count[1]);
 for(unsigned i=0;i<sizeof(expected_entries)/sizeof(expected_entries[0]);i++){ExpectedEntry& e=expected_entries[i];size_t n=strlen(e.bytes)/2;BYTE b[24]={};char actual[49]={};bool got=n<=24&&rpm(process,e.address,b,n);if(got)for(unsigned j=0;j<n;j++)sprintf(actual+j*2,"%02x",b[j]);if(i)printf(",");printf("{\"address\":\"0x%x\",\"expected\":\"%s\",\"actual\":\"%s\",\"restored\":%s}",e.address,e.bytes,got?actual:"",got&&!strcmp(e.bytes,actual)?"true":"false");}
 puts("]}");CloseHandle(process);delete s;return 0;
}
