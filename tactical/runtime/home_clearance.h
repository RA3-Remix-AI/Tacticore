#pragma once
#include <cstdint>

namespace tacticore::runtime {
// Passive paired-census wire contract. This is endpoint vacancy only.
constexpr uint32_t home_clearance_header_kind=32;
constexpr uint32_t home_clearance_node_kind=33;
constexpr uint32_t home_clearance_own_kind=34;
constexpr uint32_t home_clearance_max_nodes=20000;
constexpr uint32_t home_clearance_max_group_rows=640,home_clearance_trace_budget=2800;
constexpr uint32_t home_clearance_unknown=0,home_clearance_clear=1,home_clearance_occupied=2;
}
