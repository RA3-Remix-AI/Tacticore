#pragma once
#include <windows.h>
#include <stdint.h>
static const uint32_t MAGIC=0x4d464150, MESSAGE=WM_APP+0x342;
#define STRINGIFY_INNER(x) #x
#define STRINGIFY(x) STRINGIFY_INNER(x)
#ifdef PROBE_EPOCH
static_assert(PROBE_EPOCH>=1&&PROBE_EPOCH<=999,"bounded probe epoch");
#endif
#ifdef MACRO_BUILD_AIRFIELD
static const char FLAG_NAME[]="/5TFMacro_57e668b44d8943bdbc920dd436f046ef_P3_build_airfield";
static const char MAPPING_PREFIX[]="Local\\RA3MacroAirfieldV" STRINGIFY(PROBE_EPOCH) "_";
static const char LIBRARY_NAME[]="MacroAirfieldV" STRINGIFY(PROBE_EPOCH) ".dll";
static const uint32_t LIFETIME_MS=210000;
#elif defined(MACRO_SCOUT_STATE)
static const char FLAG_NAME[]="/5TFMacro_57e668b44d8943bdbc920dd436f046ef_P3_scout";
#ifdef PROBE_EPOCH
static const char MAPPING_PREFIX[]="Local\\RA3MacroScoutStateV" STRINGIFY(PROBE_EPOCH) "_";
static const char LIBRARY_NAME[]="MacroScoutStateV" STRINGIFY(PROBE_EPOCH) ".dll";
#else
static const char MAPPING_PREFIX[]="Local\\RA3MacroScoutState_";
static const char LIBRARY_NAME[]="MacroScoutState.dll";
#endif
static const uint32_t LIFETIME_MS=45000;
#else
static const char FLAG_NAME[]="/TFMacroFlagABI_57e668b44d8943bdbc920dd436f046ef_P3";
static const char MAPPING_PREFIX[]="Local\\RA3MacroFlagABI_";
static const char LIBRARY_NAME[]="MacroFlagABI.dll";
static const uint32_t LIFETIME_MS=15000;
#endif
// Diagnostic builds use an unreferenced name. Scout builds expose exactly one
// native strategic-state gate, and still expose no arbitrary script/action API.
struct Shared {
 uint32_t magic,version,pid,thread,start_low,start_high,owner,ai,personality,personality_id,player_template,engine;
 volatile LONG request,ack,phase,active;
 uint32_t error,attempted,callback_thread,start_tick,start_frame,last_frame,before,after,cleanup_verified,watchdog_requested;
};
