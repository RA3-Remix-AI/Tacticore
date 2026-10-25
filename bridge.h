#pragma once
#define _WIN32_WINNT 0x0601
#include <windows.h>
#include <stdint.h>
#define BRIDGE_MESSAGE (WM_APP + 0x319)
#define BRIDGE_MAGIC 0x52413342u
struct Request {
    uint32_t magic, operation, thing, owner, hash;
    float target[3];
    volatile LONG done;
    uint32_t result, thread, actual_owner, actual_hash, ai;
    float before[3], hp;
};

