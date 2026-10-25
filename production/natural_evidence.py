"""Accept only observed native production sources for passive thread evidence.

0x200 is an observed native batch flag, never an authorization for active use.
Active enqueue remains the separately verified single-unit flag 0.
"""
KNOWN_CALLERS=frozenset({0x4f467a,0x4f49e7})
KNOWN_FLAGS=frozenset({0,0x200})
def integer(value):
 if type(value) is int:return value
 if type(value) is str:return int(value,0)
 raise ValueError('invalid_native_integer')
def compatible_natural_calls(observation,pid):
 if observation.get('pid')!=pid:raise RuntimeError('natural_process_mismatch')
 if observation.get('state')!=2 or observation.get('error')!=0 or observation.get('original_bytes_restored') is not True or observation.get('active_detours')!=0:raise RuntimeError('natural_observer_not_restored')
 thread=observation.get('window_thread')
 if type(thread) is not int or thread<=0 or observation.get('callback_thread')!=thread:raise RuntimeError('natural_control_thread_mismatch')
 accepted=[]
 for event in observation.get('events',[]):
  try:
   args=event.get('raw_args_after_template')
   valid=type(args) is list and len(args)==7 and all(type(x) is int for x in args) and args[0] in KNOWN_FLAGS and args[1:]==[0xcd7e84,0,0,0,0,0] and integer(event['caller']) in KNOWN_CALLERS and event.get('thread')==thread and integer(event['matched_node'])>0 and type(event.get('return_value')) is int and event['return_value']>0 and type(event.get('node_cost')) is int and event['node_cost']>0
  except (KeyError,ValueError,TypeError):valid=False
  if valid:accepted.append(event)
 if not accepted:raise RuntimeError('natural_production_thread_missing')
 return accepted
