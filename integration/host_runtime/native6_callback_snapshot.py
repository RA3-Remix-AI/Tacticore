"""Read a completed publication from the admitted, aligned Native6 mapping.

Native6's sole x86 callback publishes active=1, increments serial, performs
guard/service, then publishes active=0. Aligned 32-bit loads bracket the SDK
copy so a torn memcpy alone cannot certify completion. This is not a world
snapshot, an identity authority, or a replacement for build admission.
"""
import ctypes as c


def completed_snapshot(state):
    cls=type(state)
    if (not isinstance(state,c.Structure) or c.sizeof(cls)!=4592
            or cls.active.offset!=4356 or cls.callback_serial.offset!=4580):
        raise ValueError('native6_completed_snapshot_layout_changed')
    base=c.addressof(state)
    if base%4:raise ValueError('native6_completed_snapshot_unaligned')
    def scalar(offset):return c.c_uint32.from_address(base+offset).value
    serial=scalar(4580)
    if scalar(4356):return None
    value=cls.from_buffer_copy(c.string_at(base,4592))
    active_after=scalar(4356);serial_after=scalar(4580)
    if (active_after or serial!=serial_after or value.active
            or value.callback_serial!=serial or not 0<=serial<0xffffffff):return None
    return value
