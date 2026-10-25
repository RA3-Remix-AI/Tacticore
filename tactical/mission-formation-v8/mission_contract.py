"""Pure MF8 input binding. Native ABI and physical policy are not guessed here.

The host supplies opaque actor/contact identities and a frozen deadline only.
Positions, routes, breadcrumbs, weapon handles and restoration are never model
or file assertions. The trusted wrapper reads them from the bound live scene.
"""
import re
import uuid

MODE='native_leader_actual_breadcrumbs'
FIELDS=frozenset({'schema_version','session_id','pid','player_id','front_id',
                  'support_id','navigation_mode','target_contact_id','expires_frame'})


def positive_int(value,code):
    if type(value) is not int or not 0<value<=0xffffffff:raise ValueError(code)
    return value


def validate_mission(value,session,front_id,support_id,*,target_contact_id,
                     now_frame,expires_frame,lease_frames=4500):
    if not isinstance(value,dict) or set(value)!=FIELDS:raise ValueError('mission_identity_fields')
    if type(value['schema_version']) is not int or value['schema_version']!=1:raise ValueError('mission_schema')
    if not isinstance(session,dict):raise ValueError('mission_session_binding')
    try:
        session_id=str(uuid.UUID(session['session_id']))
        if value['session_id']!=session_id:raise ValueError('mission_session_binding')
    except (TypeError,KeyError,AttributeError,ValueError):raise ValueError('mission_session_binding') from None
    positive_int(session.get('pid'),'mission_session_binding')
    if type(value['pid']) is not int or value['pid']!=session['pid'] or type(value['player_id']) is not int or value['player_id']!=3:raise ValueError('mission_player_binding')
    positive_int(front_id,'mission_actor_binding');positive_int(support_id,'mission_actor_binding')
    if front_id==support_id or type(value['front_id']) is not int or type(value['support_id']) is not int or value['front_id']!=front_id or value['support_id']!=support_id:raise ValueError('mission_actor_binding')
    if value['navigation_mode']!=MODE:raise ValueError('mission_navigation_mode')
    if not isinstance(target_contact_id,str) or not re.fullmatch(r'[A-Za-z0-9_:\-]{1,96}',target_contact_id) or value['target_contact_id']!=target_contact_id:raise ValueError('mission_explicit_contact_binding')
    positive_int(now_frame,'mission_deadline');positive_int(expires_frame,'mission_deadline')
    if type(value['expires_frame']) is not int or value['expires_frame']!=expires_frame or not 300<=expires_frame-now_frame<=4500 or type(lease_frames) is not int or not 300<=lease_frames<=4500:raise ValueError('mission_deadline')
    return dict(value,lease_frames=min(lease_frames,expires_frame-now_frame))
