"""Only unfinished STOPs may enter the original orphan collector.

A released normal/no-attachment contract is reviewed by the passive normal
reader. An invalid committed proof stays unverified; it is not silently replaced
by another protocol or fresh capture. No existing record/file is rewritten here.
"""
from .journal import JournalError
from .native6_orphan_return import KIND as ORPHAN, recover_after_stop as collect_orphan
from .native6_history import verified_return as review_return


def recover_after_stop(backend,row,binding,receipt,atomic):
    try:stop=backend.journal.get_command(row['run_id'],'macro-stop')
    except JournalError:stop=None
    if stop is not None:
        if stop['status']=='released':
            if (stop['receipt'] or {}).get('native_release_contract')!=ORPHAN:return False
            return review_return(backend,row,binding,receipt)
        elif stop['status'] not in {'reserved','dispatching','accepted','started','uncertain'}:return False
    return collect_orphan(backend,row,binding,receipt,atomic)
