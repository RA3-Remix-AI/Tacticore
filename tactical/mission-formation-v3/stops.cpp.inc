static void __attribute__((fastcall)) stop_facade_hook(void* self,void*,uint32_t source){
 InterlockedIncrement(&p->active);bool front=(uintptr_t)self==p->update+0x24,support=(uintptr_t)self==p->support.update+0x24;
 if(front||support){if(!tag){if(front&&role_leased(false))p->native_stop++;else if(support&&role_leased(true))p->support.native_stop++;}event(30,source,(uintptr_t)__builtin_return_address(0),0,0,0,support);}
 old_stop_facade(self,source);if(front||support)event(31,source,0,0,0,0,support);InterlockedDecrement(&p->active);
}
static void __attribute__((fastcall)) stop_private_hook(void* self,void*,uint32_t source){
 InterlockedIncrement(&p->active);bool front=(uintptr_t)self==p->update,support=(uintptr_t)self==p->support.update;uint32_t caller=(uintptr_t)__builtin_return_address(0);
 if(front||support){event(32,source,caller,0,0,0,support);}old_stop_private(self,source);
 if(front){p->total_private_stops++;if((p->phase==1||p->phase==7)&&source==1&&caller==0x787791){if(p->lease_stage==3&&p->phase==1)p->prepare_reconstituted_stops++;else if(p->stop_calls){p->private_stop_calls++;p->private_stop_frame=frame();}}event(33,source,caller);}
 if(support){if((p->phase==1||p->phase==7)&&source==1&&caller==0x787791&&p->support.stop_calls){p->support.private_stop_calls++;p->support.private_stop_frame=frame();}event(33,source,caller,0,0,0,1);}
 InterlockedDecrement(&p->active);
}
