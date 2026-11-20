#pragma once

#include <stdint.h>

// Finite high-level enemy preference. This core has no process opener, native
// address, unit selector, build/production interface, coordinate or Game IO.
// The adapter must provide fresh, identity-bound own-selector samples and the
// reviewed native SetPriority / AutomaticScheme calls. Offline tests establish
// core transitions only. Native admission and independent return are separate.
namespace ra3_enemy_focus_v1 {

// Player ids are the native player-list indexes 0..15. Any number of enemies
// and allies (human or AI) may be present; only mutual enemies are focusable.
const uint32_t MAX_PLAYERS = 16;

enum class Phase : uint32_t {
    Empty = 0,
    Held = 1,
    ApplyUnknown = 2,
    RestoreUnknown = 3,
    BaselineObserved = 4,
    RestoreOnly = 5,
    Blocked = 6,
};

enum class Result : uint32_t {
    Rejected = 0,
    Adopted = 1,
    Restored = 2,
    Unknown = 3,
    Waiting = 4,
};

struct Snapshot {
    uint32_t selector;
    uint32_t automatic_scheme;
    uint32_t manual;
    uint32_t isolated;
    uint32_t enumeration_lock;
    uint32_t own_player;            // From the bound owner; informational.
    uint32_t enemy_mask;            // Bit i: player id i and the own player are mutual enemies.
    uint32_t alive_mask;            // Bit i: participant i is present and not defeated.
    uint32_t priority[MAX_PLAYERS]; // Selector priority per player id, absent entries are 0.
    bool binding_matches;
    bool paused;
    uint32_t frame;
    uint32_t callback;
    uint64_t ms;
};

inline uint32_t focusable(const Snapshot& value) { return value.enemy_mask & value.alive_mask; }

inline uint32_t bit(uint32_t player) { return player < MAX_PLAYERS ? 1u << player : 0u; }

struct Audit {
    uint32_t request;
    Phase phase;
    uint32_t target_player;
    uint32_t selector;
    uint32_t baseline_scheme;
    uint32_t deadline_frame;
    uint64_t deadline_ms;
    uint32_t call_reservations;
    Snapshot observed;
};

class Environment {
public:
    virtual ~Environment() = default;
    virtual bool sample(Snapshot& value) = 0;
    virtual bool persist(const Audit& value) = 0;
    virtual bool set_priority(uint32_t selector, uint32_t player, uint32_t priority) = 0;
    virtual bool restore_automatic(uint32_t selector, uint32_t scheme) = 0;
};

class Lease {
public:
    explicit Lease(Environment& environment) : environment_(environment) {}

    Phase phase() const { return phase_; }
    uint32_t call_reservations() const { return attempts_; }
    uint32_t target_player() const { return target_; }
    uint32_t deadline_frame() const { return deadline_frame_; }

    Result release(uint32_t request) {
        if (!request || request > 2048 || request <= request_ ||
            (phase_ != Phase::Empty && phase_ != Phase::BaselineObserved && phase_ != Phase::Held))
            return Result::Rejected;
        request_ = request;
        return service(true);
    }

    Result request(uint32_t request, uint32_t target, uint32_t not_after_frame,
                   uint32_t wall_ms) {
        if (phase_ != Phase::Empty && phase_ != Phase::BaselineObserved && phase_ != Phase::Held)
            return Result::Rejected;
        if (request == 0 || request > 2048 || request <= request_ ||
            target >= MAX_PLAYERS || wall_ms == 0 || wall_ms > 60000)
            return Result::Rejected;

        Snapshot before = {};
        if (!sample(before) || before.paused || before.enumeration_lock ||
            !(focusable(before) & bit(target)) || not_after_frame <= before.frame ||
            not_after_frame - before.frame > 900 || before.ms > UINT64_MAX - wall_ms)
            return Result::Rejected;
        if (phase_ == Phase::Held ? !held(before) : !baseline(before))
            return Result::Rejected;

        // Capture only an automatic native baseline. Another manual owner is
        // never overwritten or claimed. Initial qualification covers Medium's
        // native Flat scheme. The hostile set is fixed with the baseline.
        if (!selector_) {
            selector_ = before.selector;
            baseline_scheme_ = before.automatic_scheme;
            enemy_mask_ = before.enemy_mask;
        }
        const bool renew = phase_ == Phase::Held && target == target_;
        const bool retarget = phase_ == Phase::Held && target != target_;
        request_ = request;
        target_ = target;
        deadline_frame_ = not_after_frame;
        deadline_ms_ = before.ms + wall_ms;
        phase_ = Phase::ApplyUnknown;
        reconciliation_pending_ = false;
        if (!audit(before)) return Result::Unknown;

        if (retarget) {
            // Two native high-level calls form an explicitly partial operation.
            // Every attempt is durable before the call. Any uncertain result
            // enters read-only reconciliation, followed only by cleanup.
            if (!prepare_call(before, false)) return Result::Unknown;
            if (!environment_.restore_automatic(selector_, baseline_scheme_)) return Result::Unknown;
            if (!sample(before) || !baseline(before)) return Result::Unknown;
        }
        if (!renew) {
            if (!prepare_call(before, false)) return Result::Unknown;
            if (!environment_.set_priority(selector_, target_, 10)) return Result::Unknown;
        }
        if (!sample(before) || !held(before) || before.frame >= deadline_frame_ || before.ms >= deadline_ms_)
            return Result::Unknown;
        phase_ = Phase::Held;
        held_alive_mask_ = alive_mask(before);
        if (!audit(before)) {
            phase_ = Phase::ApplyUnknown;
            return Result::Unknown;
        }
        return Result::Adopted;
    }

    Result service(bool stopping) {
        if (phase_ == Phase::Blocked) return Result::Unknown;
        if (phase_ == Phase::Empty || phase_ == Phase::BaselineObserved) return Result::Restored;
        if (phase_ == Phase::ApplyUnknown || phase_ == Phase::RestoreUnknown)
            return reconcile();
        Snapshot value = {};
        if (!sample(value)) return Result::Waiting;
        if (phase_ == Phase::Held && known_public_elimination(value))
            return restore(value);
        if ((phase_ == Phase::Held && !held(value)) ||
            (phase_ == Phase::RestoreOnly && !same_selector_state(value, reconciliation_))) {
            phase_ = Phase::ApplyUnknown;
            reconciliation_pending_ = false;
            return Result::Unknown;
        }
        if (phase_ == Phase::RestoreOnly || stopping || value.frame >= deadline_frame_ ||
            value.ms >= deadline_ms_ || !(focusable(value) & bit(target_)))
            return restore(value);
        return Result::Adopted;
    }

    bool independently_eligible_for_return() {
        if (phase_ == Phase::Empty) return true;
        Snapshot value = {};
        return phase_ == Phase::BaselineObserved && sample(value) && baseline(value) &&
               !value.enumeration_lock && value.callback > last_baseline_.callback &&
               value.frame >= last_baseline_.frame && value.ms > last_baseline_.ms;
    }

private:
    Environment& environment_;
    Phase phase_ = Phase::Empty;
    uint32_t selector_ = 0;
    uint32_t baseline_scheme_ = 2;
    uint32_t enemy_mask_ = 0;
    uint32_t request_ = 0;
    uint32_t target_ = 0;
    uint32_t deadline_frame_ = 0;
    uint64_t deadline_ms_ = 0;
    uint32_t attempts_ = 0;
    uint32_t held_alive_mask_ = 0;
    uint32_t last_frame_ = 0;
    uint32_t last_callback_ = 0;
    uint64_t last_ms_ = 0;
    bool reconciliation_pending_ = false;
    Snapshot reconciliation_ = {};
    Snapshot last_baseline_ = {};

    bool sample(Snapshot& value) {
        if (!environment_.sample(value) || !value.binding_matches || !value.selector ||
            (selector_ && value.selector != selector_) || value.automatic_scheme != 2 ||
            value.manual > 1 || value.isolated > 1 || !value.frame || !value.callback ||
            value.frame < last_frame_ || value.callback < last_callback_ || value.ms < last_ms_)
            return false;
        if (value.own_player >= MAX_PLAYERS || (value.enemy_mask & bit(value.own_player)) ||
            (value.enemy_mask >> MAX_PLAYERS) || (value.alive_mask >> MAX_PLAYERS) ||
            (selector_ && value.enemy_mask != enemy_mask_))
            return false;
        for (uint32_t i = 0; i < MAX_PLAYERS; ++i) {
            if (value.priority[i] > 10) return false;
            if (value.priority[i] && !(value.enemy_mask & bit(i))) return false;
        }
        last_frame_ = value.frame;
        last_callback_ = value.callback;
        last_ms_ = value.ms;
        return true;
    }

    // Native automatic selection lists every living enemy with priority 1.
    static bool automatic_priorities(const Snapshot& value, uint32_t except) {
        const uint32_t expected = focusable(value);
        for (uint32_t i = 0; i < MAX_PLAYERS; ++i) {
            if (i != except && value.priority[i] != ((expected >> i) & 1u)) return false;
        }
        return true;
    }

    bool baseline(const Snapshot& value) const {
        return value.automatic_scheme == baseline_scheme_ && !value.manual && !value.isolated &&
               automatic_priorities(value, MAX_PLAYERS);
    }

    bool held(const Snapshot& value) const {
        return target_ < MAX_PLAYERS && value.manual == 1 && value.isolated == 0 &&
               value.priority[target_] == 10 && automatic_priorities(value, target_);
    }

    static uint32_t alive_mask(const Snapshot& value) { return focusable(value); }

    bool known_public_elimination(const Snapshot& value) const {
        const uint32_t current = alive_mask(value);
        if (current == held_alive_mask_ || (current & ~held_alive_mask_) ||
            value.manual != 1 || value.isolated != 0)
            return false;
        // Native may remove a defeated public participant's entry before or
        // after this callback. Either representation ends this preference and
        // restores automatic selection, allowing a later model reassessment.
        for (uint32_t index = 0; index < MAX_PLAYERS; ++index) {
            const uint32_t expected = index == target_ ? 10 : 1;
            if (current & bit(index)) {
                if (value.priority[index] != expected) return false;
            } else if (value.priority[index] != 0 &&
                       (!(held_alive_mask_ & bit(index)) || value.priority[index] != expected)) {
                return false;
            }
        }
        return true;
    }

    bool audit(const Snapshot& value) {
        Audit row = {};
        row.request = request_;
        row.phase = phase_;
        row.target_player = target_;
        row.selector = selector_;
        row.baseline_scheme = baseline_scheme_;
        row.deadline_frame = deadline_frame_;
        row.deadline_ms = deadline_ms_;
        row.call_reservations = attempts_;
        row.observed = value;
        return environment_.persist(row);
    }

    bool prepare_call(Snapshot& value, bool restoring) {
        // This is a durable call reservation. A subsequent failed guard can
        // leave it unconsumed. Fresh binding, pause, lock and original intent
        // bounds are checked again after the durable attempt record.
        const Snapshot expected = value;
        ++attempts_;
        if (!audit(value) || !sample(value) || value.enumeration_lock ||
            !same_selector_state(expected, value)) return false;
        return restoring || (!value.paused && (focusable(value) & bit(target_)) &&
                             value.frame < deadline_frame_ && value.ms < deadline_ms_);
    }

    Result restore(Snapshot& value) {
        if (value.enumeration_lock) return Result::Waiting;
        phase_ = Phase::RestoreUnknown;
        reconciliation_pending_ = false;
        if (!prepare_call(value, true)) return Result::Unknown;
        if (!environment_.restore_automatic(selector_, baseline_scheme_)) return Result::Unknown;
        if (!sample(value) || !baseline(value)) return Result::Unknown;
        return record_baseline(value);
    }

    Result record_baseline(const Snapshot& value) {
        phase_ = Phase::BaselineObserved;
        deadline_frame_ = 0;
        deadline_ms_ = 0;
        last_baseline_ = value;
        if (!audit(value)) {
            phase_ = Phase::RestoreUnknown;
            reconciliation_pending_ = false;
            return Result::Unknown;
        }
        return Result::Restored;
    }

    static bool same_selector_state(const Snapshot& a, const Snapshot& b) {
        if (a.selector != b.selector || a.automatic_scheme != b.automatic_scheme ||
            a.manual != b.manual || a.isolated != b.isolated ||
            a.enemy_mask != b.enemy_mask || a.alive_mask != b.alive_mask)
            return false;
        for (uint32_t i = 0; i < MAX_PLAYERS; ++i) {
            if (a.priority[i] != b.priority[i]) return false;
        }
        return true;
    }

    Result reconcile() {
        Snapshot value = {};
        if (!sample(value) || value.enumeration_lock) return Result::Waiting;
        if (!reconciliation_pending_ || !same_selector_state(value, reconciliation_)) {
            reconciliation_ = value;
            reconciliation_pending_ = audit(value);
            return Result::Waiting;
        }
        if (value.callback <= reconciliation_.callback || value.frame <= reconciliation_.frame ||
            value.ms <= reconciliation_.ms)
            return Result::Waiting;
        if (!audit(value)) return Result::Waiting;
        reconciliation_pending_ = false;
        if (baseline(value)) return record_baseline(value);
        if (phase_ == Phase::RestoreUnknown) {
            phase_ = Phase::Blocked;
            audit(value);
            return Result::Unknown;
        }
        // An uncertain application is never replayed. The separate cleanup
        // operation becomes eligible only after two fresh matching samples.
        phase_ = Phase::RestoreOnly;
        return Result::Waiting;
    }
};

} // namespace ra3_enemy_focus_v1
