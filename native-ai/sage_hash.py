"""32-bit SAGE UTF-8 identifier checksum for offline asset verification.

Pure arithmetic implementation; no SDK, reference script or process access.
Historical reference-script hashes remain evidence data, never an import path.
"""
import struct

def sage_hash(value):
    data=value.encode('utf-8');length=len(data);mask=(1<<32)-1
    if not length:return 0
    if length==10 and data[:2]==b'0x':return int(value[2:],16)&mask
    state=length;stop=length-length%4
    for first,second in struct.iter_unpack('<HH',data[:stop]):
        state=(state+first)&mask
        state^=((second^((state<<5)&mask))<<11)&mask
        state=(state+(state>>11))&mask
    tail=data[stop:]
    if len(tail)==3:
        state=(state+int.from_bytes(tail[:2],'little'))&mask
        state^=((state^((tail[2]<<2)&mask))<<16)&mask
        state=(state+(state>>11))&mask
    elif len(tail)==2:
        state=(state+int.from_bytes(tail,'little'))&mask
        state^=(state<<11)&mask
        state=(state+(state>>17))&mask
    elif tail:
        state=(state+tail[0])&mask
        state^=(state<<10)&mask
        state=(state+(state>>1))&mask
    for shift,right in ((3,False),(5,True),(2,False),(15,True),(10,False)):
        state=((state+(state>>shift)) if right else (state^(state<<shift)))&mask
    return state
