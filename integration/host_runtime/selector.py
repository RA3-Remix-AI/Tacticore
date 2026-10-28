"""Deterministic target proposals with complete rejection diagnostics.

This module consumes a host's current own-FOV projection. Selection is a proposal,
not a grant: a real adapter must still validate identity, capabilities and sight.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Mapping, Sequence


@dataclass(frozen=True)
class SelectionProfile:
    name: str = "static_ground_current_fov_v1"
    min_distance: float = 450
    max_distance: float = 2000
    min_hp: float = 600
    max_age_frames: int = 60
    roles: tuple[str, ...] = ("structure", "economy")
    economy_templates: tuple[str, ...] = ("0xc45aaeab",)
    forbidden_template_words: tuple[str, ...] = ("BaseDefense", "Turret", "Wall")
    threat_radius: float = 350
    threat_penalty: float = 400

    def __post_init__(self):
        values = (self.min_distance, self.max_distance, self.min_hp,
                  self.threat_radius, self.threat_penalty)
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
            raise ValueError("invalid_selection_profile")
        if self.min_distance > self.max_distance or type(self.max_age_frames) is not int or self.max_age_frames < 0:
            raise ValueError("invalid_selection_profile")
        if not self.name or not self.roles or any(not isinstance(r, str) or not r for r in self.roles):
            raise ValueError("invalid_selection_profile")


@dataclass(frozen=True)
class SelectionResult:
    selected: dict | None
    diagnostics: tuple[dict, ...]
    rejection_counts: dict[str, int]
    profile: str
    reason_code: str
    selection_only: bool = True
    authority_granted: bool = False

    def public(self) -> dict:
        return {"selected": self.selected, "diagnostics": list(self.diagnostics),
                "rejection_counts": dict(self.rejection_counts), "profile": self.profile,
                "reason_code": self.reason_code, "selection_only": True,
                "authority_granted": False}


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) not in (2, 3):
        return None
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in value):
        return None
    return tuple(float(v) for v in value)


def select_target(contacts: Sequence[Mapping], anchors: Sequence[Sequence[float]], *,
                  game_frame: int, own_view_verified: bool,
                  profile: SelectionProfile | None = None) -> SelectionResult:
    """Return a stable proposal and reasons for *every* rejected input row.

    Expected projection fields are contact_id, object_id, relation,
    currently_visible, observed_frame, xyz, hp, role, type_hash and template.
    No hidden contact is used even as a nearby-threat ranking input.
    """
    profile = profile or SelectionProfile()
    if type(game_frame) is not int or game_frame < 0:
        raise ValueError("invalid_game_frame")
    if not isinstance(contacts, (list, tuple)) or any(not isinstance(c, Mapping) for c in contacts):
        raise ValueError("invalid_contacts")
    points = [_point(p) for p in anchors] if isinstance(anchors, (list, tuple)) else []
    boundary_reason = "own_view_unverified" if own_view_verified is not True else None
    if not points or any(p is None for p in points):
        boundary_reason = boundary_reason or "invalid_anchors"
    counts = Counter(c.get("contact_id") for c in contacts if isinstance(c.get("contact_id"), str))
    diagnostics = []
    candidates = []
    threats = []
    for index, row in enumerate(contacts):
        contact_id = row.get("contact_id")
        reason = boundary_reason
        xyz = _point(row.get("xyz"))
        observed = row.get("observed_frame")
        hp = row.get("hp")
        if reason is None:
            if not isinstance(contact_id, str) or not contact_id or type(row.get("object_id")) is not int or row["object_id"] <= 0:
                reason = "invalid_contact_identity"
            elif counts[contact_id] > 1:
                reason = "duplicate_contact_id"
            elif row.get("relation") != "enemy":
                reason = "not_enemy"
            elif row.get("currently_visible") is not True:
                reason = "not_currently_visible"
            elif type(observed) is not int or observed < 0 or observed > game_frame:
                reason = "invalid_observation_frame"
            elif game_frame - observed > profile.max_age_frames:
                reason = "observation_expired"
            elif xyz is None:
                reason = "invalid_position"
            elif type(hp) not in (int, float) or not math.isfinite(hp) or hp <= 0:
                reason = "not_alive"
        fresh = reason is None
        # Diagnostics must not leak a distance calculated from hidden/stale rows.
        distance = min(math.dist(xyz[:2], p[:2]) for p in points) if fresh else None
        template = row.get("template", "")
        if not isinstance(template, str):
            template = ""
        if fresh and (row.get("role") in ("armor", "air") or any(w in template for w in ("BaseDefense", "Turret"))):
            threats.append((row.get("object_id"), xyz))
        if reason is None:
            if row.get("role") not in profile.roles:
                reason = "unsupported_target_role"
            elif row.get("role") == "economy" and row.get("type_hash") not in profile.economy_templates:
                reason = "unsupported_economy_template"
            elif distance < profile.min_distance:
                reason = "target_too_near"
            elif distance > profile.max_distance:
                reason = "target_too_far"
            elif hp < profile.min_hp:
                reason = "target_hp_below_profile"
            elif any(word in template for word in profile.forbidden_template_words):
                reason = "forbidden_template"
        diagnostic = {"input_index": index, "contact_id": contact_id,
                      "object_id": row.get("object_id"), "reason_code": reason or "eligible",
                      "distance": distance, "observed_frame": observed,
                      "age_frames": game_frame - observed if type(observed) is int else None}
        diagnostics.append(diagnostic)
        if reason is None:
            # Explicit allowlist: unknown projection fields never become dispatch data.
            selected = {key: row.get(key) for key in ("contact_id", "object_id", "owner_player_id", "role", "type_hash", "template", "observed_frame")}
            selected.update(xyz=list(xyz), hp=hp, currently_visible=True, relation="enemy")
            candidates.append((selected, distance, diagnostic))
    ranked = []
    for selected, distance, diagnostic in candidates:
        pressure = sum(1 for identity, xyz in threats if identity != selected["object_id"] and math.dist(xyz[:2], selected["xyz"][:2]) <= profile.threat_radius)
        score = distance + profile.threat_penalty * pressure
        diagnostic.update(visible_nearby_threats=pressure, score=score)
        ranked.append((score, distance, selected["contact_id"], selected["object_id"], selected))
    chosen = min(ranked, default=None, key=lambda r: r[:4])
    rejected = Counter(d["reason_code"] for d in diagnostics if d["reason_code"] != "eligible")
    if not contacts:
        rejected[boundary_reason or "no_contacts"] += 1
    return SelectionResult(chosen[-1] if chosen else None, tuple(diagnostics),
                           dict(sorted(rejected.items())), profile.name,
                           "selected" if chosen else boundary_reason or "no_eligible_target")
