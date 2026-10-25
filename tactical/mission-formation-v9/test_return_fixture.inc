// Actual common normal_return, only Transfer facade replaced by in-memory fake.
static void normal_return(){
 invalidate_move_tickets(4);
 if(unit()&&!p->return_calls){tag=3;p->return_calls++;fake_transfer((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->unit,1);p->return_verified=unit()&&word(p->unit+0x414)==p->default_team;event(5);tag=0;}
 if(support_valid()&&!p->support.return_calls){tag=3;p->support.return_calls++;fake_transfer((void*)(uintptr_t)p->owner,(void*)(uintptr_t)p->support.thing,1);p->support.returned=support_valid()&&word(p->support.thing+0x414)==p->default_team;event(5,0,0,0,0,0,1);tag=0;}
 if(!p->return_verified||!p->support.returned)p->error=p->error?p->error:37;
 p->returned_frame=frame();p->return_pending=0;p->phase=2;
}
