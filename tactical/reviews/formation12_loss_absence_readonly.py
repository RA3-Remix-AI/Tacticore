"""Collect inert headers and two advancing complete absence scans; no SDK calls.

This is an independent diagnostic sidecar, never a runtime capability or Return.
The original terminal report, native disposal flag and qualifier remain unchanged.
"""
import argparse, ctypes, hashlib, importlib.util, json, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def collect(report_path, session_path, output):
    source = report_path.read_bytes()
    session_bytes = session_path.read_bytes()
    report = json.loads(source.decode('utf-8-sig'))
    session = json.loads(session_bytes.decode('utf-8-sig'))
    folder = ROOT / 'tactical/mission-formation-v12'
    wrapper = load('mf12_loss_frozen_wrapper', folder / 'lease.py')
    helper = load('mf12_loss_frozen_scan', ROOT / 'tactical/readonly_disposal.py')
    native = report['native']
    assert wrapper.frozen_sources_match(report)
    assert session['pid'] == report['preflight']['pid'] == native['pid']
    assert session['session_id'] == report['session_id'] == native['session_id']
    assert native['phase'] == 4 and native['error'] == 52
    assert native['active'] == 0 and native['restore_mask'] == 131071
    assert native['detach_calls'] == 1 and native['return_calls'] == 0
    record = dict(protocol='mf12_loss_absence_readonly_v1', reader_sha256=sha(__file__),
        source_report=str(report_path.resolve()), source_sha256=sha(report_path),
        session_sha256=sha(session_path), session_id=session['session_id'], pid=session['pid'],
        object_id=native['object_id'], sdk_calls=0, mutations=False, completed=False,
        goal_observed=False, return_verified=False, stance_restored=False,
        runtime_capability_granted=False, snapshots=[], scans=[])
    memory = wrapper.b.Memory(session['pid'], session)
    def snapshot():
        terminal = wrapper.terminal_readonly(memory, report)
        assert terminal['binding_verified'] and terminal['timer'] == terminal['active'] == 0
        assert terminal['phase'] == 4 and terminal['error'] == 52
        assert terminal['restore_mask'] == 131071 and len(terminal['entries']) == 17
        assert all(e['actual'] == e['expected'] for e in terminal['entries'])
        layout = json.loads((folder / 'inert-layout.json').read_text())
        header, pointer, timer = wrapper.read_stable_header(memory, int(terminal['module_base'], 0), layout)
        assert header.object_id == native['object_id'] and header.unit == native['unit']
        assert header.type_hash == native['type_hash'] and header.update == native['update']
        return dict(terminal=terminal, header_hex=bytes(header).hex(), pointer=pointer, timer=timer)
    try:
        record['snapshots'].append(snapshot())
        deadline = time.monotonic() + 18
        while time.monotonic() < deadline and len(record['scans']) < 2:
            assert report_path.read_bytes() == source and session_path.read_bytes() == session_bytes
            try:
                scan = helper.live_scan(memory, native['logic'], native['object_id'])
                if not record['scans'] or scan['frame'] > record['scans'][-1]['end_frame']:
                    record['scans'].append(scan)
            except ValueError as error:
                record['last_scan_error'] = str(error)
            if len(record['scans']) < 2:
                time.sleep(.08)
        record['snapshots'].append(snapshot())
        assert report_path.read_bytes() == source and session_path.read_bytes() == session_bytes
    except Exception as error:
        record['collection_error'] = type(error).__name__ + ':' + str(error)
    finally:
        memory.close()
    record['diagnostic_absence_observed'] = (not record.get('collection_error') and
        len(record['scans']) == 2 and len(record['snapshots']) == 2 and
        record['scans'][0]['end_frame'] < record['scans'][1]['frame'] and
        record['snapshots'][0]['header_hex'] == record['snapshots'][1]['header_hex'])
    with output.open('x', encoding='utf-8') as handle:
        json.dump(record, handle, indent=2, allow_nan=False)
    print(json.dumps(dict(output=str(output), sha256=sha(output),
        diagnostic_absence_observed=record['diagnostic_absence_observed'],
        scans=[s['frame'] for s in record['scans']], error=record.get('collection_error'))))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--session', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    collect(args.report, args.session, args.output)
