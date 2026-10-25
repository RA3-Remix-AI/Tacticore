# Pydantic real-provider memory probe: independent review

**Passed within the explicitly simulated mission scope.** Two real DeepSeek requests/responses through the Pydantic backend were accepted, without retry. The actual maximum serialized request was15457 bytes, within16384.

The request-context append log matches both recorded context hashes exactly. Snapshots2/116s and40/170s each join to their own request, accepted plan and valid-policy decision records. At170s the same canonical mission/task/target and deadline280 remain present, with20 events compacted. This is beyond the original100s seed plan's maximum45-second TTL. The persisted memory still contains that mission in approach with progress revision2. The100s seed and all execution feedback are synthetic; there are zero real game commands or effect claims.

Three additional offline tests exercise the actual default factory/PydanticAI/OpenAI SDK path with explicit MockTransport: multiple accepted plans through compaction, a429 failure followed by local continuation and a later accepted plan, and a cancelled deadline followed by recovery. No external network is available to those tests, no mission is redispatched or prematurely completed, and metadata logs contain no credential or provider-body fields.

This does not substitute for a real full-match lifecycle audit. Actual game snapshots, one native dispatch, physical effects, safe withdrawal/release and a real accepted postTTL compressed context must still be verified in the formal match. No extra provider request, key read/copy or game command was made by this reviewer.

The final synthetic stop retains the in-flight mission with host_stop/restoration_pending and no terminal success. This is conservative shutdown bookkeeping, not proof of native restoration or a completed lifecycle.
