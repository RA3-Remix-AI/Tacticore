"""Offline APT disassembly via pySAGE's MIT converter, game files unchanged.

Reference: https://github.com/ClementJ18/pySAGE/tree/master/sage_apt
Only extracted research data is passed to the converter; no viewer/server run.
"""
import json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'frontend-reference/pySAGE-master'))
from sage_apt.aptfile import apt_bytes_to_xml
from validate_side_imports import read_stream
def main():
    report=[]
    for file in (ROOT/'frontend-assets').glob('*.manifest'):
        stream=read_stream(file);blobs={}
        for row in stream['rows']:
            kind=row['name'].split(':')[0]
            if kind not in ['AptAptData','AptConstData']:continue
            data=stream['files']['bin'][row['binary_offset']:row['binary_offset']+row['binary_size']]
            ptr,size=struct.unpack_from('<II',data,4);blobs[kind]=data[ptr:ptr+size]
        if len(blobs)!=2:continue
        output=file.with_suffix('.xml')
        try:
            xml=apt_bytes_to_xml(blobs['AptAptData'],blobs['AptConstData']);output.write_bytes(xml)
            report.append(dict(source=str(file),output=str(output),success=True))
        except Exception as error:report.append(dict(source=str(file),success=False,error=str(error)))
    (ROOT/'frontend-assets/decompile-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
