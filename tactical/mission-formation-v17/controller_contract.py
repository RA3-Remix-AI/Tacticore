"""Pure MF13 controller and write-once commit contract; no process access."""
import ctypes as c
import hashlib,math,struct,uuid
FIELDS={'schema_version','controller_id','lease_id','formation_uuid','formation_version','seq','startup_deadline_frame','startup_wall_ms','slots'}
SLOT_FIELDS={'role','command_id','task_id','seq','unit','cost','factory','factory_id','iface'}
UNITS=(('conscript',0x19ab11af,85),('flak',0x2c358c61,220))

def uid(value):
 if type(value) is not str:raise ValueError('controller_uuid')
 result=uuid.UUID(value)
 if not result.int:raise ValueError('controller_uuid')
 return str(result)

def uint(value,code='controller_uint',minimum=1):
 if type(value) is not int or not minimum<=value<=0xffffffff:raise ValueError(code)
 return value

def pointer(value):
 if type(value) is str:
  try:value=int(value,0)
  except ValueError:raise ValueError('controller_pointer') from None
 uint(value,'controller_pointer',0x10000)
 if value&3:raise ValueError('controller_pointer')
 return value

def words(value):return struct.unpack('<4I',uuid.UUID(uid(value)).bytes)

def formation_ids(controller_id):
 native=str(uuid.uuid5(uuid.UUID(uid(controller_id)),'paid_pair'))
 return native,'formation_'+uuid.UUID(native).hex[:16]

def validate_controller(value,now_frame):
 if type(value) is not dict or set(value)!=FIELDS:raise ValueError('controller_fields')
 if type(value['schema_version']) is not int or value['schema_version']!=1 or type(value['formation_version']) is not int or value['formation_version']!=1:raise ValueError('controller_schema')
 result=dict(value)
 for key in ('controller_id','lease_id','formation_uuid'):result[key]=uid(value[key])
 if result['controller_id']==result['lease_id'] or result['formation_uuid']!=formation_ids(result['controller_id'])[0]:raise ValueError('controller_outer_identity')
 uint(result['seq']);uint(now_frame)
 if type(value['startup_deadline_frame']) is not int or not now_frame<value['startup_deadline_frame']<=now_frame+900:raise ValueError('controller_startup_frame')
 if type(value['startup_wall_ms']) is not int or not 1000<=value['startup_wall_ms']<=60000:raise ValueError('controller_startup_wall')
 if type(value['slots']) is not list or len(value['slots'])!=2:raise ValueError('controller_two_slots')
 slots=[];seen={result['controller_id'],result['lease_id'],result['formation_uuid']}
 for role,(slot,unit) in enumerate(zip(value['slots'],UNITS)):
  if type(slot) is not dict or set(slot)!=SLOT_FIELDS or type(slot['role']) is not int or slot['role']!=role:raise ValueError('controller_slot_fields')
  if slot['unit']!=unit[0] or type(slot['cost']) is not int or slot['cost']!=unit[2]:raise ValueError('controller_paid_pair_scope')
  item=dict(slot,command_id=uid(slot['command_id']),task_id=uid(slot['task_id']))
  if item['command_id'] in seen or item['task_id'] in seen or item['command_id']==item['task_id']:raise ValueError('controller_slot_uuid_reused')
  seen.update((item['command_id'],item['task_id']));uint(item['seq']);uint(item['factory_id'])
  item['factory']=pointer(item['factory']);item['iface']=pointer(item['iface']);item['unit_hash']=unit[1];slots.append(item)
 if slots[0]['seq']>=slots[1]['seq']:raise ValueError('controller_production_sequence')
 result['slots']=slots
 return result

def seal_body(body):
 offset=type(body).digest_sha256.offset
 if offset!=252 or c.sizeof(body)!=284:raise ValueError('controller_commit_layout')
 prefix=bytes(body)[:offset];digest=hashlib.sha256(prefix).digest()
 body.digest_sha256[:]=struct.unpack('<8I',digest)
 return dict(commit_prefix_hex=prefix.hex(),commit_body_hex=bytes(body).hex(),digest_sha256=digest.hex(),digest_encoding='sha256_native_little_endian_body_prefix_252_v1')

def verify_body(body):
 try:
  digest=hashlib.sha256(bytes(body)[:type(body).digest_sha256.offset]).digest()
  return c.sizeof(body)==284 and type(body).digest_sha256.offset==252 and struct.pack('<8I',*body.digest_sha256)==digest
 except (AttributeError,TypeError,ValueError,struct.error):return False
