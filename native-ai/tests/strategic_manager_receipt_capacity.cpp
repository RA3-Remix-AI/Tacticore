#include "../strategic_manager_gate_enable_candidate_v2.h"
#include <cassert>
#include <cstdio>
#include <map>

namespace gate = ra3_strategic_manager_enable_candidate_v2;

class FakeGame final : public gate::Environment {
    std::map<uint32_t, uint8_t> bytes;

    void write_word(uint32_t address, uint32_t value) {
        for (unsigned i = 0; i != 4; ++i) {
            bytes[address + i] = static_cast<uint8_t>(value >> (i * 8));
        }
    }

public:
    gate::Binding binding{};
    unsigned records = 0;
    unsigned calls = 0;

    FakeGame() {
        binding.pid = 7;
        binding.callback_thread = 8;
        binding.creation_filetime = 9;
        binding.owner = 0x10000;
        binding.ai = 0x12000;
        binding.personality = 0x14000;
        binding.personality_data = 0x16000;
        binding.player_template = 0x18000;
        binding.game = 0x1a000;
        binding.engine = 0x1c000;

        const uint32_t manager = 0x1e000;
        const uint32_t store = 0x20000;
        const uint32_t profiles = 0x22000;
        const uint32_t sides = 0x24000;
        const uint32_t opening = 0x26000;

        for (const auto &pin : gate::CODE_PINS) {
            for (size_t i = 0; i * 2 < ::strlen(pin.hex); ++i) {
                unsigned value;
                assert(std::sscanf(pin.hex + i * 2, "%2x", &value) == 1);
                bytes[pin.address + static_cast<uint32_t>(i)] = static_cast<uint8_t>(value);
            }
        }
        write_word(0xcd8ce4, binding.game);
        write_word(binding.game, 0xbeb630);
        write_word(binding.game + 0x50, 24000);
        write_word(0xcdd190, binding.engine);
        write_word(0xcdd1a0, manager);
        write_word(manager, 0xc07ab8);
        write_word(manager + 0x48, binding.owner);
        write_word(0xce98ec, store);
        write_word(store, 0xc606b8);
        write_word(store + 0x24, profiles);
        write_word(store + 0x28, profiles + 4);
        write_word(profiles, binding.personality);
        write_word(binding.owner, 0xc5bce0);
        write_word(binding.owner + 0x20, 3);
        write_word(binding.owner + 0x10, binding.player_template);
        write_word(binding.owner + 0x90, binding.ai);
        write_word(binding.ai, 0xc60f60);
        write_word(binding.ai + 8, binding.owner);
        write_word(binding.ai + 0x8a8, binding.owner);
        write_word(binding.ai + 0x8b0, binding.personality);
        write_word(binding.personality, binding.personality_data);
        write_word(binding.personality + 0x18, 0x799613e0);
        write_word(binding.personality_data + 0xec, 1);
        write_word(binding.personality_data + 0xf0, sides);
        write_word(sides, binding.player_template);
        write_word(binding.ai + 0x5e8, opening);
        write_word(opening, 0xc5f378);
        write_word(opening + 0x18, binding.owner);
        for (const auto &component : gate::COMPONENTS) {
            const auto address = binding.ai + component.offset;
            write_word(address, component.vtable);
            write_word(address + component.owner_offset, binding.owner);
            bytes[address + component.enabled_offset] = 1;
        }
    }

    bool read(uint32_t address, void *target, size_t size) override {
        auto *out = static_cast<uint8_t *>(target);
        for (size_t i = 0; i != size; ++i) {
            const auto found = bytes.find(address + static_cast<uint32_t>(i));
            out[i] = found == bytes.end() ? 0 : found->second;
        }
        return true;
    }

    bool os_identity(gate::OsIdentity &actual) override {
        actual = {binding.pid, binding.callback_thread, 0x400000, binding.creation_filetime, 800000000};
        return true;
    }

    bool verify_bound_inputs_and_common_lease(const gate::Binding &) override { return true; }
    bool journal(const gate::Audit &) override { ++records; return true; }

    gate::Outcome normal_component_call(uint32_t, uint32_t, bool) override {
        ++calls;
        return gate::Outcome::Unknown;
    }
};

int main() {
    constexpr uint64_t transport_limit = 2048;
    constexpr auto production = gate::Gate::UnitAndPrerequisiteFamily;
    FakeGame game;
    gate::Candidate manager(game, game.binding);
    for (uint64_t request = 1; request <= transport_limit; ++request) {
        const auto result = manager.request_enable(production, request, 780, 52000);
        if (result != gate::Result::StateAlreadySatisfiedObserved) {
            std::fprintf(stderr, "request %llu returned %u\n",
                         static_cast<unsigned long long>(request), static_cast<unsigned>(result));
            return 1;
        }
    }
    assert(manager.request_enable(production, 1, 780, 52000) == gate::Result::StateAlreadySatisfiedObserved);
    assert(manager.request_enable(production, 1, 781, 52000) == gate::Result::Rejected);
    assert(manager.request_enable(production, transport_limit + 1, 780, 52000) == gate::Result::Rejected);
    assert(game.records == transport_limit);
    assert(game.calls == 0);
    return 0;
}
