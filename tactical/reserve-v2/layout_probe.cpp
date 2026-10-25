#include "shared.h"
#include <stdio.h>
#include <stddef.h>
int main(){printf("{\"sample\":%u,\"move_proof\":%u,\"event\":%u,\"rally\":%u,\"rally_offset\":%u,\"events\":%u,\"tactical\":%u}\n",(unsigned)sizeof(Sample),(unsigned)sizeof(MoveProof),(unsigned)sizeof(Event),(unsigned)sizeof(RallyState),(unsigned)offsetof(Probe,rally),(unsigned)offsetof(Probe,events),(unsigned)sizeof(Probe));}
