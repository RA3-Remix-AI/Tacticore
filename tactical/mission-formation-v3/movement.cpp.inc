static void __attribute__((fastcall)) move_hook(void* self,void*,float* xyz,void* path,float limit,uint32_t source){
 InterlockedIncrement(&p->active);bool front=(uintptr_t)self==p->update,support=(uintptr_t)self==p->support.update;
 if(front||support){if(!tag){if(front&&role_leased(false))p->native_move++;else if(support&&role_leased(true))p->support.native_move++;}event(10,source,(uintptr_t)__builtin_return_address(0),0,0,0,support,xyz,(uintptr_t)path,limit);}
 old_move(self,xyz,path,limit,source);if(front||support)event(11,source,0,0,0,0,support,xyz,(uintptr_t)path,limit);InterlockedDecrement(&p->active);
}
static void __attribute__((fastcall)) move_facade_hook(void* self,void*,float* xyz,uint32_t source){
 InterlockedIncrement(&p->active);bool front=(uintptr_t)self==p->update+0x24,support=(uintptr_t)self==p->support.update+0x24;
 if(front||support)event(50,source,(uintptr_t)__builtin_return_address(0),0,0,0,support,xyz);
 old_move_facade(self,xyz,source);if(front||support)event(51,source,0,0,0,0,support,xyz);InterlockedDecrement(&p->active);
}
