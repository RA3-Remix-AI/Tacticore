"""Address table for direct unit control (round 2). All addresses for this feature live here.

Every entry targets the bound game binary (``GAME_SHA``, retail 1.12 layout, ImageBase 0x400000) and names
where its evidence comes from. ``entry_bytes`` is the byte check done before any call; ``None`` means the
bytes still have to be read once on the Windows machine by ``unit_control_precheck.py`` and pinned here.
"""

IMAGE_BASE = 0x400000
RETAIL_SIZE_OF_IMAGE = 0x93B000
STEAM_SIZE_OF_IMAGE = 0x950000

# Ra3-Copilot commit these addresses were taken from (https://github.com/ProbiusOfficial/Ra3-Copilot).
RA3_COPILOT_COMMIT = "d8abf9ecb0306f8b4a0b87a6cafa07ffd3dbcbd2"
# The one binary Ra3-Copilot's own address table was made from (its README, "受支持的二进制").
RA3_COPILOT_GAME_SHA = "518ef27297d490590f0315b6143cc7ab0010bf606d2f351ca64d447c3f7b0221"

FUNCTIONS = {
    # thiscall AIUpdate*, Coord3D*, CommandSource. Same VA in native-symbols.json (our binary) and in
    # Ra3-Copilot src/aicmd.cpp RVA_MOVE (retail column).
    "move_to_position": dict(
        va=0x6EFF70,
        entry_bytes=bytes.fromhex("568bf18b4e3c8b018b5038ffd2d9057cd4c0008b44240851"),
        source="native-ai/native-symbols.json privateMoveToPosition; Ra3-Copilot aicmd.cpp RVA_MOVE",
    ),
    # thiscall AIUpdate*, Thing* victim, int max_shots, CommandSource. Ra3-Copilot aicmd.cpp RVA_ATTACK.
    "attack_object": dict(
        va=0x76E690,
        entry_bytes=None,
        source="Ra3-Copilot aicmd.cpp RVA_ATTACK (retail column); not yet in native-symbols.json",
    ),
}

# Thing vtable used to recognise live objects when enumerating memory (Ra3-Copilot battlefield.cpp).
THING_VTABLE = dict(va=0xC4DB60, source="Ra3-Copilot battlefield.cpp kThingVtFallback")

# Field offsets inside a Thing (runtime only; cannot be checked offline). Ra3-Copilot battlefield.cpp/aicmd.cpp.
THING_TEMPLATE = 0x04  # -> template; template+0x08 is the type hash
THING_AI_UPDATE = 0x374  # -> AIUpdateInterface, the `this` of the two functions above
THING_OWNER = 0x418  # -> owning player/team object

# CommandSource passed by Ra3-Copilot: 0 = player. Kept as is so R1 measures what R2 will send.
COMMAND_SOURCE_PLAYER = 0
