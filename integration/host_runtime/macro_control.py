"""Current product boundary: strategic decisions, native AI unit operation.

This policy grants no new native capability. Historical unit-control evidence
must not enable micro in a newly constructed Host or desktop readiness check.
"""
from .contracts import ContractError

CONTROL_MODE = "macro_native"
UNIT_CONTROL_EVIDENCE = (
    "tactical_evidence", "runtime_report", "runtime_sha256",
    "runtime_recovery_report", "runtime_recovery_sha256",
)


def require_macro_configuration(args):
    mode = getattr(args, "control_mode", CONTROL_MODE)
    if mode != CONTROL_MODE:
        raise ContractError("unsupported_control_mode")
    require_macro_evidence(args)
    return CONTROL_MODE


def require_macro_evidence(registration):
    if any(getattr(registration, field, None) is not None for field in UNIT_CONTROL_EVIDENCE):
        raise ContractError("macro_mode_rejects_unit_control_evidence")


MODEL_BOUNDARY = (
    "The model makes macro decisions; original native AI performs unit movement, "
    "local targeting, combat and abilities. No individual unit control, leases, "
    "Move/Hold/Return or per-shot tasks are available. Use only currently listed "
    "verified macro capabilities. Production uses its existing real queue and "
    "payment contract. Construction, scouting, technology and force deployment "
    "must remain unsupported until their native high-level consumer is verified. "
    "Unknown resources and unseen enemy information remain unknown."
)
