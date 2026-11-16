#include "../strategic_enemy_focus_lease_v1.h"
#include <assert.h>
#include <stdio.h>
#include <vector>

namespace focus = ra3_enemy_focus_v1;

struct Environment : focus::Environment {
    focus::Snapshot value = {};
    std::vector<focus::Audit> journal;
    unsigned calls = 0;
    unsigned automatic_calls = 0;
    bool set_returns = true;
    bool set_mutates = true;
    bool restore_returns = true;
    bool restore_mutates = true;
    bool audit_returns = true;
    bool expire_on_attempt = false;
    bool change_identity_on_attempt = false;
    bool change_selector_on_attempt = false;

    Environment() {
        value.selector = 0x10000;
        value.automatic_scheme = 2;
        value.priority[0] = value.priority[1] = 1;
        value.opponent_alive[0] = value.opponent_alive[1] = true;
        value.binding_matches = true;
        value.frame = 100;
        value.callback = 10;
        value.ms = 1000;
    }

    void advance() {
        ++value.frame;
        ++value.callback;
        ++value.ms;
    }

    bool sample(focus::Snapshot& result) override {
        result = value;
        return true;
    }

    bool persist(const focus::Audit& row) override {
        journal.push_back(row);
        if (row.call_reservations) {
            if (expire_on_attempt) value.frame = row.deadline_frame;
            if (change_identity_on_attempt) value.binding_matches = false;
            if (change_selector_on_attempt) value.priority[1] = 9;
        }
        return audit_returns;
    }

    bool set_priority(uint32_t selector, uint32_t player, uint32_t priority) override {
        assert(selector == value.selector && (player == 4 || player == 5) && priority == 10);
        assert(!journal.empty() && journal.back().phase == focus::Phase::ApplyUnknown);
        assert(journal.back().call_reservations == calls + automatic_calls + 1);
        ++calls;
        if (set_mutates) {
            value.manual = 1;
            value.priority[player - 4] = priority;
        }
        return set_returns;
    }

    bool restore_automatic(uint32_t selector, uint32_t scheme) override {
        assert(selector == value.selector && scheme == 2);
        assert(!journal.empty());
        assert(journal.back().call_reservations == calls + automatic_calls + 1);
        ++automatic_calls;
        if (restore_mutates) {
            value.manual = value.isolated = 0;
            value.priority[0] = uint32_t(value.opponent_alive[0]);
            value.priority[1] = uint32_t(value.opponent_alive[1]);
        }
        return restore_returns;
    }
};

static void adoption_renewal_retarget_and_stop() {
    Environment env;
    focus::Lease lease(env);
    assert(lease.request(1, 4, 900, 30000) == focus::Result::Adopted);
    assert(env.calls == 1 && lease.target_player() == 4);
    env.advance();
    assert(lease.request(2, 4, 950, 30000) == focus::Result::Adopted);
    assert(env.calls == 1 && lease.deadline_frame() == 950);
    assert(lease.request(2, 4, 950, 30000) == focus::Result::Rejected);
    env.advance();
    assert(lease.request(3, 5, 990, 30000) == focus::Result::Adopted);
    assert(env.calls == 2 && env.automatic_calls == 1);
    assert(env.value.priority[0] == 1 && env.value.priority[1] == 10);
    assert(lease.service(true) == focus::Result::Restored);
    assert(env.automatic_calls == 2 && !lease.independently_eligible_for_return());
    env.advance();
    assert(lease.independently_eligible_for_return());
}

static void unknown_apply_is_read_only_until_separate_cleanup() {
    Environment env;
    env.set_returns = false;
    focus::Lease lease(env);
    assert(lease.request(1, 4, 900, 30000) == focus::Result::Unknown);
    assert(env.calls == 1 && lease.phase() == focus::Phase::ApplyUnknown);
    assert(lease.request(2, 4, 950, 30000) == focus::Result::Rejected);
    assert(lease.service(true) == focus::Result::Waiting);
    assert(lease.service(true) == focus::Result::Waiting);
    assert(env.automatic_calls == 0);
    env.advance();
    assert(lease.service(true) == focus::Result::Waiting);
    assert(lease.phase() == focus::Phase::RestoreOnly);
    assert(env.automatic_calls == 0);
    assert(lease.service(true) == focus::Result::Restored);
    assert(env.calls == 1 && env.automatic_calls == 1);
}

static void uncertain_restore_is_never_replayed(bool mutation) {
    Environment env;
    focus::Lease lease(env);
    assert(lease.request(1, 4, 900, 30000) == focus::Result::Adopted);
    env.restore_returns = false;
    env.restore_mutates = mutation;
    assert(lease.service(true) == focus::Result::Unknown);
    assert(lease.phase() == focus::Phase::RestoreUnknown && env.automatic_calls == 1);
    assert(lease.service(true) == focus::Result::Waiting);
    env.advance();
    const focus::Result result = lease.service(true);
    if (mutation) {
        assert(result == focus::Result::Restored);
        env.advance();
        assert(lease.independently_eligible_for_return());
    } else {
        assert(result == focus::Result::Unknown && lease.phase() == focus::Phase::Blocked);
        for (unsigned i = 0; i < 100; ++i) {
            env.advance();
            assert(lease.service(true) == focus::Result::Unknown);
        }
        assert(!lease.independently_eligible_for_return());
    }
    assert(env.automatic_calls == 1 && env.calls == 1);
}

static void uncertain_retarget_keeps_cleanup_separate() {
    for (unsigned failure = 0; failure < 2; ++failure) {
        Environment env;
        focus::Lease lease(env);
        assert(lease.request(1, 4, 900, 30000) == focus::Result::Adopted);
        env.advance();
        if (failure == 0) env.restore_returns = false;
        if (failure == 1) env.set_returns = false;
        assert(lease.request(2, 5, 950, 30000) == focus::Result::Unknown);
        assert(lease.request(3, 5, 990, 30000) == focus::Result::Rejected);
        const unsigned writes = env.calls + env.automatic_calls;
        assert(lease.service(true) == focus::Result::Waiting);
        env.advance();
        const focus::Result reconciled = lease.service(true);
        assert(env.calls + env.automatic_calls == writes);
        if (failure == 0) {
            assert(reconciled == focus::Result::Restored);
            assert(env.calls == 1 && env.automatic_calls == 1);
        } else {
            assert(reconciled == focus::Result::Waiting);
            assert(lease.phase() == focus::Phase::RestoreOnly);
            assert(lease.service(true) == focus::Result::Restored);
            assert(env.calls == 2 && env.automatic_calls == 2);
        }
        env.advance();
        assert(lease.independently_eligible_for_return());
    }
}

static void invalid_requests_cannot_mutate() {
    for (unsigned i = 0; i < 11; ++i) {
        Environment env;
        focus::Lease lease(env);
        uint32_t target = 4, deadline = 900, wall = 30000;
        if (i == 0) target = 3;
        if (i == 1) target = 6;
        if (i == 2) deadline = 100;
        if (i == 3) deadline = 1001;
        if (i == 4) wall = 60001;
        if (i == 5) env.value.paused = true;
        if (i == 6) env.value.enumeration_lock = 1;
        if (i == 7) env.value.binding_matches = false;
        if (i == 8) env.value.opponent_alive[0] = false;
        if (i == 9) env.value.manual = 1;
        if (i == 10) env.value.automatic_scheme = 1;
        assert(lease.request(1, target, deadline, wall) == focus::Result::Rejected);
        assert(env.calls == 0 && env.automatic_calls == 0 && env.journal.empty());
    }
}

static void durable_boundary_rechecks() {
    for (unsigned i = 0; i < 4; ++i) {
        Environment env;
        focus::Lease lease(env);
        if (i == 0) env.audit_returns = false;
        if (i == 1) env.expire_on_attempt = true;
        if (i == 2) env.change_identity_on_attempt = true;
        if (i == 3) env.change_selector_on_attempt = true;
        assert(lease.request(1, 4, 900, 30000) == focus::Result::Unknown);
        assert(env.calls == 0 && env.automatic_calls == 0);
        assert(lease.phase() == focus::Phase::ApplyUnknown);
        assert(lease.request(2, 5, 950, 30000) == focus::Result::Rejected);
    }
}

static void finite_expiry_pause_cleanup_and_regression() {
    Environment env;
    focus::Lease lease(env);
    assert(lease.request(1, 4, 900, 30000) == focus::Result::Adopted);
    env.value.frame = 900;
    env.value.paused = true;
    assert(lease.service(false) == focus::Result::Restored);
    assert(env.automatic_calls == 1);
    env.advance();
    assert(lease.independently_eligible_for_return());
    env.value.paused = false;
    --env.value.frame;
    assert(lease.request(2, 5, 950, 30000) == focus::Result::Rejected);
    assert(env.calls == 1);

    Environment wall;
    focus::Lease wall_lease(wall);
    assert(wall_lease.request(1, 4, 900, 50) == focus::Result::Adopted);
    wall.value.ms += 50;
    assert(wall_lease.service(false) == focus::Result::Restored);
    assert(wall.automatic_calls == 1);
}

static void changed_state_on_stop_requires_reconciliation() {
    Environment env;
    focus::Lease lease(env);
    assert(lease.request(1, 4, 900, 30000) == focus::Result::Adopted);
    env.value.priority[1] = 9;
    assert(lease.service(true) == focus::Result::Unknown);
    assert(env.automatic_calls == 0);
    assert(lease.service(true) == focus::Result::Waiting);
    env.advance();
    assert(lease.service(true) == focus::Result::Waiting);
    assert(lease.phase() == focus::Phase::RestoreOnly);
    env.value.priority[1] = 8;
    assert(lease.service(true) == focus::Result::Unknown);
    assert(env.automatic_calls == 0);
    assert(lease.service(true) == focus::Result::Waiting);
    env.advance();
    assert(lease.service(true) == focus::Result::Waiting);
    assert(lease.service(true) == focus::Result::Restored);
    assert(env.automatic_calls == 1);
}

static void public_elimination_restores_then_allows_the_surviving_enemy() {
    for (unsigned eliminated = 0; eliminated < 2; ++eliminated) {
        for (unsigned removed = 0; removed < 2; ++removed) {
            Environment env;
            focus::Lease lease(env);
            assert(lease.request(1, 4, 900, 30000) == focus::Result::Adopted);
            env.value.opponent_alive[eliminated] = false;
            if (removed) env.value.priority[eliminated] = 0;
            assert(lease.service(false) == focus::Result::Restored);
            assert(env.automatic_calls == 1 && lease.phase() == focus::Phase::BaselineObserved);
            env.advance();
            assert(lease.independently_eligible_for_return());
            const uint32_t survivor = eliminated == 0 ? 5 : 4;
            assert(lease.request(2, survivor, 950, 30000) == focus::Result::Adopted);
            assert(env.calls == 2 && lease.target_player() == survivor);
        }
    }
}

int main() {
    adoption_renewal_retarget_and_stop();
    unknown_apply_is_read_only_until_separate_cleanup();
    uncertain_restore_is_never_replayed(false);
    uncertain_restore_is_never_replayed(true);
    uncertain_retarget_keeps_cleanup_separate();
    invalid_requests_cannot_mutate();
    durable_boundary_rechecks();
    finite_expiry_pause_cleanup_and_regression();
    changed_state_on_stop_requires_reconciliation();
    public_elimination_restores_then_allows_the_surviving_enemy();
    puts("enemy focus lease offline tests passed; Game access=0; native calls=0");
}
