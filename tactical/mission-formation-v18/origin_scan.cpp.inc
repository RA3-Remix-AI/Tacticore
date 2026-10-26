// Complete current-visible-enemy origin proof, never reading hidden XYZ/HP.
// Typed bounded word stream is chunked into existing Event.stack_words.
static uint32_t origin_words[65536],origin_used,origin_generation,origin_event_words[128];
static uint32_t origin_footprint[4096][3];
static bool origin_overflow;static uint32_t origin_last_generation[2];
static int origin_grid_index13(float coordinate,float origin,float scale){volatile float delta=coordinate-origin;volatile float product=delta*scale;if(!isfinite(product)||product< -2147483648.f||product>=2147483648.f)return (-2147483647-1);return (int)product;}
static void origin_add(uint32_t w){if(origin_used<65536)origin_words[origin_used++]=w;else origin_overflow=true;}
static uint32_t origin_read(uint32_t address){uint32_t value=word(address);origin_add(value);return value;}
static bool origin_cell(uint32_t cell){origin_add(cell);uint16_t count=0;BYTE flag=1;if(!read(cell+10,&count,2)||!read(cell+0x32,&flag,1))return false;origin_add(count);origin_add(flag);return !flag&&count;}
static void origin_emit13(uint32_t kind,uint32_t role,uint32_t generation,uint32_t offset,uint32_t count,uint32_t result){memset(origin_event_words,0,512);origin_event_words[0]=0x4f533133;origin_event_words[1]=1;origin_event_words[2]=generation;origin_event_words[3]=role;origin_event_words[4]=frame();origin_event_words[5]=offset;origin_event_words[6]=count;origin_event_words[7]=result;if(count)memcpy(origin_event_words+8,origin_words+offset,count*4);event(kind,generation,0,0,0,0,role,NULL,0,0,origin_event_words);}
static bool origin_scan13(uint32_t role,const ReserveSample13& own){
 origin_used=0;origin_overflow=false;uint32_t now=frame(),generation=++origin_generation;origin_last_generation[role]=generation;
 // stream header20words: magic,frame,role,ownThing/ID/owner/XYZ,head,impl/grid.
 origin_add(0x4f533133);origin_add(now);origin_add(role);origin_add(own.thing);origin_add(own.id);origin_add(p->owner);uint32_t xyzbits[3];memcpy(xyzbits,own.xyz,12);for(unsigned i=0;i<3;i++)origin_add(xyzbits[i]);
 uint32_t head=word(p->logic+0xb4);origin_add(head);uint32_t manager=word(0xce2fa0),impl=word(manager+0x28);origin_add(manager);origin_add(word(manager));origin_add(impl);
 uint32_t cells=word(impl+0x44),width=word(impl+0x3c),height=word(impl+0x40),origin[2]={},scaleBits=word(impl+0x38),fallback=word(0xd074a4);read(impl+4,origin,8);origin_add(cells);origin_add(width);origin_add(height);origin_add(origin[0]);origin_add(origin[1]);origin_add(scaleBits);origin_add(fallback);
 float gridOrigin[2],scale;memcpy(gridOrigin,origin,8);memcpy(&scale,&scaleBits,4);bool valid=word(manager)==0xc6aefc&&cells&&width&&height&&width<=4096&&height<=4096&&width*height<=4000000&&isfinite(scale)&&scale>0&&scale<=10&&isfinite(gridOrigin[0])&&isfinite(gridOrigin[1])&&(fallback==0||fallback==1||fallback==3)&&now==own.frame;
 uint32_t t=head,nodes=0,authorized=0;float minimum=3.402823466e+38F;bool clear=true;
 while(valid&&t){
  if(t%4||++nodes>2048||word(t)!=0xc4db60){valid=false;break;}
  origin_add(0x4e4f4445);origin_add(t);uint32_t vt=origin_read(t),id=origin_read(t+0xdc),owner=origin_read(t+0x418),next=origin_read(t+0x7c),mask=origin_read(t+0xc8);if(!id||next==t){valid=false;break;}
  uint32_t ownerVT=owner?word(owner):0,index=owner?word(owner+0x20):0;origin_add(ownerVT);origin_add(index);
  // result codes:0 own/unowned/non-enemy,1 hidden/stealth,2 authorized visible,3 invalid.
  uint32_t result_index=origin_used;origin_add(0);bool enemy=false;
  if(owner&&owner!=p->owner){
   if(ownerVT!=0xc5bce0||index>=20){valid=false;origin_words[result_index]=3;break;}
   uint32_t rel=word(p->owner+0xfc),buckets=word(rel+8),count=word(rel+0xc),sentinel=word(rel+0x10);origin_add(rel);origin_add(buckets);origin_add(count);origin_add(sentinel);
   if(!rel||!sentinel){origin_add(0);origin_add(0x454e4452);}
   else {
    if(!buckets||!count||count>4096){valid=false;break;}
    uint32_t node=word(buckets+(index%count)*4),chain=0;origin_add(node);
    while(node){if(node%4||++chain>100){valid=false;break;}uint32_t key=word(node),value=word(node+4),n=word(node+8);origin_add(node);origin_add(key);origin_add(value);origin_add(n);if(key==index){if(value>2)valid=false;else enemy=value==0;break;}if(n==node){valid=false;break;}node=n;}
    // Native Player::844680: a completed missing-key traversal is neutral.
    origin_add(0x454e4452);if(!valid)break;
   }
  }
  if(enemy){
   uint32_t record=word(t+0x9c),recordImpl=word(record),first=word(record+0x1c),num=word(record+0x20);BYTE pending=1,masked=1;read(record+0xf8,&pending,1);read(record+0xf9,&masked,1);origin_add(record);origin_add(recordImpl);origin_add(first);origin_add(num);origin_add(pending);origin_add(masked);
   if(record&&recordImpl!=impl){valid=false;break;}if(num>4096||(num&&!first)){valid=false;break;}
   bool visible=!(mask&((1u<<11)|(1u<<12)))&&record&&recordImpl==impl&&!pending&&!masked&&first&&num&&num<=4096;
   if(visible){
    uint32_t start=origin_used;origin_add(0);uint32_t total=0;
    for(uint32_t i=0;i<num;i++){uint32_t cell=word(first+16*i);origin_add(i);origin_add(cell);origin_footprint[i][0]=cell;if(!cell){origin_footprint[i][1]=0;origin_footprint[i][2]=1;origin_add(0);origin_add(1);continue;}if(cell<cells||(cell-cells)%0x34||(cell-cells)/0x34>=width*height){valid=false;break;}uint16_t c=0;BYTE flag=1;read(cell+10,&c,2);read(cell+0x32,&flag,1);origin_add(c);origin_add(flag);origin_footprint[i][1]=c;origin_footprint[i][2]=flag;total++;if(flag||!c||(c==0xffff&&fallback!=1))visible=false;}
    origin_words[start]=total;if(!total)visible=false;
    // Revalidate every footprint read before authorizing any position read.
    origin_add(0x464f4f54);origin_add(word(t+0x9c));origin_add(word(record));origin_add(word(record+0x1c));origin_add(word(record+0x20));BYTE againPending=1,againMasked=1;read(record+0xf8,&againPending,1);read(record+0xf9,&againMasked,1);origin_add(againPending);origin_add(againMasked);
    if(word(t+0x9c)!=record||word(record)!=impl||word(record+0x1c)!=first||word(record+0x20)!=num||againPending!=pending||againMasked!=masked)valid=false;
    for(uint32_t i=0;i<num;i++){uint32_t cell=word(first+16*i);uint16_t c=0;BYTE flag=1;if(cell){read(cell+10,&c,2);read(cell+0x32,&flag,1);}origin_add(cell);origin_add(c);origin_add(flag);if(cell!=origin_footprint[i][0]||c!=origin_footprint[i][1]||flag!=origin_footprint[i][2])valid=false;}
   }
   if(!valid)break;
   if(visible){
    // Only after enemy + footprint + stealth authorization do we read position.
    float xyz[3]={};uint32_t post[7]={};if(!read(t+0x38,xyz,12)||!finite_point(xyz)){valid=false;break;}
    int gx=origin_grid_index13(xyz[0],gridOrigin[0],scale),gy=origin_grid_index13(xyz[1],gridOrigin[1],scale);if(gx<0||gy<0||(uint32_t)gx>=width||(uint32_t)gy>=height){valid=false;break;}
    uint32_t center=cells+((uint32_t)gy*width+gx)*0x34;uint16_t c=0;BYTE flag=1;read(center+10,&c,2);read(center+0x32,&flag,1);origin_add(center);origin_add(c);origin_add(flag);if(flag||!c||(c==0xffff&&fallback!=1)){valid=false;break;}
    post[0]=word(t);post[1]=word(t+0xdc);post[2]=word(t+0x418);post[3]=word(t+0x7c);post[4]=word(t+0xc8);post[5]=word(t+0x9c);post[6]=word(record);for(unsigned i=0;i<7;i++)origin_add(post[i]);
    if(post[0]!=vt||post[1]!=id||post[2]!=owner||post[3]!=next||post[4]!=mask||post[5]!=record||post[6]!=impl||word(record+0x1c)!=first||word(record+0x20)!=num||frame()!=now){valid=false;break;}
    uint32_t raw[3];memcpy(raw,xyz,12);for(unsigned i=0;i<3;i++)origin_add(raw[i]);float gap=distance(own.xyz,xyz);uint32_t gapBits;memcpy(&gapBits,&gap,4);origin_add(gapBits);if(gap<minimum)minimum=gap;if(gap<=350)clear=false;authorized++;origin_words[result_index]=2;
   }else origin_words[result_index]=1;
  }
  origin_add(0x454e444e);t=next;if(origin_overflow){valid=false;break;}
 }
 uint32_t post_manager=word(0xce2fa0),post_impl=word(post_manager+0x28),post_grid[12]={post_manager,word(post_manager),post_impl,word(post_impl+0x44),word(post_impl+0x3c),word(post_impl+0x40),word(post_impl+4),word(post_impl+8),word(post_impl+0x38),word(0xd074a4),word(p->logic+0xb4),frame()};
 origin_add(0x504f5354);for(unsigned i=0;i<12;i++)origin_add(post_grid[i]);if(post_grid[0]!=manager||post_grid[1]!=0xc6aefc||post_grid[2]!=impl||post_grid[3]!=cells||post_grid[4]!=width||post_grid[5]!=height||post_grid[6]!=origin[0]||post_grid[7]!=origin[1]||post_grid[8]!=scaleBits||post_grid[9]!=fallback||post_grid[10]!=head||post_grid[11]!=now)valid=false;
 origin_add(0x454e4453);origin_add(nodes);origin_add(authorized);uint32_t minBits;memcpy(&minBits,&minimum,4);origin_add(minBits);origin_add(clear);origin_add(valid&&!origin_overflow);origin_add(frame());origin_add(word(p->logic+0xb4));
 valid=valid&&!origin_overflow&&frame()==now&&word(p->logic+0xb4)==head&&identity();uint32_t result=valid?(clear?1:2):0;
 origin_emit13(160,role,generation,0,0,result);for(uint32_t offset=0;offset<origin_used;offset+=120){uint32_t n=origin_used-offset;if(n>120)n=120;origin_emit13(161,role,generation,offset,n,result);}origin_emit13(162,role,generation,origin_used,0,result);
 return valid&&clear;
}
