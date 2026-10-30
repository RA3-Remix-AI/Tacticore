"""Read a completed publication from the admitted, aligned Native5 mapping.

Native5's sole x86 callback publishes active=1, increments serial, performs
guard/service, then publishes active=0. Aligned 32-bit loads bracket the SDK
copy so a torn memcpy alone cannot certify completion. This is not a world
snapshot, an identity authority, or a replacement for build admission.
"""
import ctypes as c


def completed_snapshot(state):
    cls=type(state)
    if (not isinstance(state,c.Structure) or c.sizeof(cls)!=1440
            or cls.active.offset!=1204 or cls.callback_serial.offset!=1428):
        raise ValueError('native5_completed_snapshot_layout_changed')
    base=c.addressof(state)
    if base%4:raise ValueError('native5_completed_snapshot_unaligned')
    def scalar(offset):return c.c_uint32.from_address(base+offset).value
    serial=scalar(1428)
    if scalar(1204):return None
    value=cls.from_buffer_copy(c.string_at(base,1440))
    active_after=scalar(1204);serial_after=scalar(1428)
    if (active_after or serial!=serial_after or value.active
            or value.callback_serial!=serial or not 0<=serial<0xffffffff):return None
    return value
