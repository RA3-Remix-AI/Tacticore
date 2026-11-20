"""Select the strategic delegation prompt version (v2 by default, v1 retained).

The version is process configuration, not model input: every component in one
process (capacity preflight, request sizing and the real send) must build the
same prompt. Set TACTICORE_PROMPT_VERSION=v1 to run the original prompt.
"""

import os

ENVIRONMENT_VARIABLE = "TACTICORE_PROMPT_VERSION"
PROMPT_VERSIONS = ("v1", "v2")
DEFAULT_PROMPT_VERSION = "v2"


class PromptVersionError(ValueError):
    """Raised for an unknown configured prompt version."""


def active_prompt_version():
    """Return the configured prompt version, failing closed on unknown values."""
    value = os.environ.get(ENVIRONMENT_VARIABLE, "").strip()
    if not value:
        return DEFAULT_PROMPT_VERSION
    if value not in PROMPT_VERSIONS:
        raise PromptVersionError("prompt_version_unsupported")
    return value


def select_prompt_version(version):
    """Make one version active for this process (used by the host CLI)."""
    if version not in PROMPT_VERSIONS:
        raise PromptVersionError("prompt_version_unsupported")
    os.environ[ENVIRONMENT_VARIABLE] = version
    return version


def delegation_prompt(version=None):
    """Return the prompt(profile, context, example, allowed, preferences) builder."""
    selected = active_prompt_version() if version is None else version
    if selected == "v1":
        from native_delegation_prompt_v1 import prompt

        return prompt
    if selected == "v2":
        from native_delegation_prompt_v2 import prompt

        return prompt
    raise PromptVersionError("prompt_version_unsupported")
