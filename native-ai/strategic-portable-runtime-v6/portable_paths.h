#pragma once
#include <shlobj.h>
#include <wincrypt.h>
#include <wchar.h>
static HMODULE portable_module;
static inline bool portable_argument(int index,wchar_t* result,size_t capacity){
 int count=0;wchar_t** values=CommandLineToArgvW(GetCommandLineW(),&count);bool okay=values&&index<count&&wcslen(values[index])<capacity;
 if(okay)wcscpy(result,values[index]);if(values)LocalFree(values);return okay;
}

static inline bool portable_plain(const wchar_t* value){
 if(!value||wcslen(value)<3||wcslen(value)>=1024||value[1]!=L':'||value[2]!=L'\\'||
    !((value[0]>=L'A'&&value[0]<=L'Z')||(value[0]>=L'a'&&value[0]<=L'z')))return false;
 wchar_t work[1024];wcscpy(work,value);unsigned begin=3;
 for(unsigned i=3;;i++)if(!work[i]||work[i]==L'\\'){
  if(i==begin||(i-begin==1&&work[begin]==L'.')||(i-begin==2&&work[begin]==L'.'&&work[begin+1]==L'.'))return false;
  wchar_t saved=work[i];work[i]=0;DWORD flags=GetFileAttributesW(work);work[i]=saved;
  if(flags==INVALID_FILE_ATTRIBUTES||(flags&FILE_ATTRIBUTE_REPARSE_POINT))return false;
  if(!saved)break;begin=i+1;
 }return true;
}
static inline bool runtime_input(const wchar_t* root,const wchar_t* relative,wchar_t* result,size_t capacity){
 if(!root||!relative||!relative[0]||relative[0]==L'/'||relative[0]==L'\\'||wcslen(root)+wcslen(relative)+2>capacity)return false;
 size_t begin=0,n=wcslen(relative);
 for(size_t i=0;i<=n;i++){
  if(relative[i]==L':'||relative[i]==L'\\')return false;
  if(i==n||relative[i]==L'/'){
   if(i==begin||(i-begin==1&&relative[begin]==L'.')||(i-begin==2&&relative[begin]==L'.'&&relative[begin+1]==L'.'))return false;
   begin=i+1;
  }
 }
 swprintf(result,capacity,L"%ls\\%ls",root,relative);
 for(wchar_t* at=result;*at;at++)if(*at==L'/')*at=L'\\';
 return portable_plain(result);
}
static inline bool portable_runtime_root(wchar_t* result,size_t capacity){
 DWORD n=GetModuleFileNameW(portable_module,result,(DWORD)capacity);
 if(!n||n>=capacity)return false;
 wchar_t* slash=wcsrchr(result,L'\\');if(!slash)return false;*slash=0;
 slash=wcsrchr(result,L'\\');if(!slash||_wcsicmp(slash+1,L"strategic6"))return false;*slash=0;
 slash=wcsrchr(result,L'\\');if(!slash||_wcsicmp(slash+1,L"native"))return false;*slash=0;
 return portable_plain(result);
}
static inline bool portable_known(REFKNOWNFOLDERID folder,const wchar_t* suffix,wchar_t* result,size_t capacity){
 PWSTR value=NULL;HRESULT status=SHGetKnownFolderPath(folder,0,NULL,&value);
 bool okay=SUCCEEDED(status)&&value&&wcslen(value)+wcslen(suffix)+1<capacity;
 if(okay){wcscpy(result,value);wcscat(result,suffix);okay=portable_plain(result);}
 if(value)CoTaskMemFree(value);return okay;
}
static inline bool portable_verify_game(const wchar_t* value){
 if(!portable_plain(value))return false;const wchar_t* name=wcsrchr(value,L'\\');
 if(!name||_wcsicmp(name+1,L"RA3_1.12.game"))return false;
 HANDLE file=CreateFileW(value,GENERIC_READ,FILE_SHARE_READ,NULL,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,NULL);
 if(file==INVALID_HANDLE_VALUE)return false;
 HCRYPTPROV provider=0;HCRYPTHASH hash=0;bool okay=false;
 if(CryptAcquireContextW(&provider,NULL,NULL,PROV_RSA_AES,CRYPT_VERIFYCONTEXT)&&CryptCreateHash(provider,CALG_SHA_256,0,0,&hash)){
  BYTE block[65536],digest[32];DWORD got=0,n=32;bool valid=true;
  for(;;){if(!ReadFile(file,block,sizeof(block),&got,NULL)){valid=false;break;}if(!got)break;if(!CryptHashData(hash,block,got,0)){valid=false;break;}}
  okay=valid&&CryptGetHashParam(hash,HP_HASHVAL,digest,&n,0)&&n==32&&!memcmp(digest,GAME_SHA,32);
 }
 if(hash)CryptDestroyHash(hash);if(provider)CryptReleaseContext(provider,0);CloseHandle(file);return okay;
}
static inline bool portable_bind_paths(const BindingWire& b){
 if(b.deployment[519]||b.game_image[519]||b.runtime_root[519]||b.journal_root[519])return false;
 wchar_t runtime[1024],journal_root[1024],mods[1024],game[1024];DWORD game_n=1024;
 if(!portable_runtime_root(runtime,1024)||_wcsicmp(runtime,b.runtime_root)||
    !portable_known(FOLDERID_LocalAppData,L"\\Tacticore\\desktop-runtime\\native6\\journals",journal_root,1024)||_wcsicmp(journal_root,b.journal_root)||
    !portable_known(FOLDERID_Documents,L"\\Red Alert 3\\Mods",mods,1024)||
    !QueryFullProcessImageNameW(GetCurrentProcess(),0,game,&game_n)||_wcsicmp(game,b.game_image))return false;
 size_t n=wcslen(mods),length=wcslen(b.deployment);
 return length>n+5&&!_wcsnicmp(b.deployment,mods,n)&&b.deployment[n]==L'\\'&&
        !_wcsicmp(b.deployment+length-4,L".big")&&portable_plain(b.deployment)&&portable_plain(b.game_image);
}
