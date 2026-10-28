// Run the original 51-group test body with the development Move/Stop lineage.
// Load the original declaration before substituting the type in the test body;
// pragma once prevents redefining either production class. No tests are copied.
#include "lineage.h"
#include "near_move_lineage.h"
#define MoveLineage NearMoveLineage
#include "test_controller.cpp"
#undef MoveLineage
