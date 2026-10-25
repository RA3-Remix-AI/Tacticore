"""Synthetic visibility and formation examples; not live capability evidence."""
from fixtures import snapshot,policy


def battlefield(at=100):
    return {"schema_version":1,"viewer_player_id":3,"visibility_verified":True,
        "regions":[{"region_id":"home_base","relation":"self","observed_at_game_seconds":at,"currently_visible":True,"role_counts":{}},{"region_id":"east_ore","relation":"enemy","observed_at_game_seconds":at,"currently_visible":True,"role_counts":{"economy":1}}],
        "contacts":[{"contact_id":"contact_ore","owner_player_id":4,"relation":"enemy","role":"economy","region_id":"east_ore","observed_at_game_seconds":at,"currently_visible":True,"stealth_state":"visible"}],
        "formations":[{"formation_id":"formation_main","version":1,"roles":{"infantry":4,"anti_air":2},"region_id":"home_base","available":True},{"formation_id":"formation_raid","version":1,"roles":{"armor":2},"region_id":"home_base","available":True}]}


def tactical_snapshot(ident=1,at=100):
    raw=snapshot(ident,at,events=[],enemy_observations=[])
    raw["battlefield"]=battlefield(at)
    return raw


def intent(module="attack",purpose="main_attack",**changes):
    raw={"module":module,"purpose":purpose,"target_region":"east_ore","target_contact_id":"contact_ore","formation_ids":["formation_main"],"required_roles":["infantry"],"force_fraction":.6}
    raw.update(changes)
    return raw


def tactical_policy(context,tasks=None,**changes):
    return policy(context,tactical_tasks=[intent()] if tasks is None else tasks,**changes)


def execution(task,**changes):
    raw={"formation_versions":dict(task.request.formation_versions),"issued_frame":1500,"expires_frame":1650,"command_source":"simulated","interference":"none","goal_observed":False,"restoration_verified":False}
    raw.update(changes)
    return raw
