// Offline Windows sharing checks against a caller-created "abc" fixture.
// This test never prepares a binding, opens Game or installs a callback.
#include "../strategic-portable-runtime-v7/native.cpp"
#include <assert.h>

int main(int argc,char** argv){
 assert(argc==2);
 wchar_t path[1024];
 assert(MultiByteToWideChar(CP_UTF8,0,argv[1],-1,path,1024)>0);
 const uint8_t expected[32]={
  0xba,0x78,0x16,0xbf,0x8f,0x01,0xcf,0xea,0x41,0x41,0x40,0xde,0x5d,0xae,0x22,0x23,
  0xb0,0x03,0x61,0xa3,0x96,0x17,0x7a,0x9c,0xb4,0x10,0xff,0x61,0xf2,0x00,0x15,0xad};
 uint8_t wrong[32]={};
 assert(!lock_hash(path,wrong));assert(input_count==0);
 assert(lock_hash(path,expected));assert(input_count==1);
 HANDLE writer=CreateFileW(path,GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
                          NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 assert(writer==INVALID_HANDLE_VALUE);assert(GetLastError()==ERROR_SHARING_VIOLATION);
 HANDLE remover=CreateFileW(path,DELETE,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
                           NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 assert(remover==INVALID_HANDLE_VALUE);assert(GetLastError()==ERROR_SHARING_VIOLATION);
 HANDLE reader=CreateFileW(path,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 assert(reader!=INVALID_HANDLE_VALUE);CloseHandle(reader);
 // The retained input remains usable for the full lifetime of its owner.
 BY_HANDLE_FILE_INFORMATION information={};
 for(unsigned i=0;i<1000;i++){
  assert(GetFileInformationByHandle(inputs[0],&information));
  assert(!(information.dwFileAttributes&(FILE_ATTRIBUTE_REPARSE_POINT|FILE_ATTRIBUTE_DIRECTORY)));
 }
 CloseHandle(inputs[0]);inputs[0]=NULL;input_count=0;
 writer=CreateFileW(path,GENERIC_WRITE,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 assert(writer!=INVALID_HANDLE_VALUE);CloseHandle(writer);
 printf("{\"passed\":true,\"checks\":[\"hash_mismatch_refused\",\"read_lock_retained\",\"write_open_blocked\",\"delete_open_blocked\",\"reader_allowed\",\"owner_close_restores_access\"],\"game_access\":false,\"native_commands\":0}\n");
 return 0;
}
