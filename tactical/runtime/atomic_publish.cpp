// Host-process-only x64 intrinsic bridge. No target process or game API.
extern "C" long _InterlockedExchange(volatile long*, long);
#pragma intrinsic(_InterlockedExchange)
extern "C" __declspec(dllexport) long runtime_exchange(volatile long* word, long value) {
    return _InterlockedExchange(word, value);
}
