"""Bounded offline SAGE manifest table reader; no analysis-tree imports."""
from pathlib import Path
import struct

def parse(path):
    with Path(path).open('rb') as source:data=source.read(64*1024*1024+1)
    if not 48<=len(data)<=64*1024*1024:raise ValueError('manifest_size_invalid')
    header=struct.unpack_from('<12I',data);count=header[3]
    if count>100000 or 48+48*count>len(data):raise ValueError('manifest_table_invalid')
    references=48+48*count;manifest_refs=references+header[8]
    names=manifest_refs+header[9];sources=names+header[10]
    if sources+header[11]!=len(data):raise ValueError('manifest_sections_invalid')
    def text(start,size,offset):
        if offset>=size:raise ValueError('manifest_string_offset_invalid')
        end=data.find(b'\0',start+offset,start+size)
        if end<0:raise ValueError('manifest_string_unterminated')
        return data[start+offset:end].decode('utf-8',errors='replace')
    rows=[];positions=[4,4,4]
    for index in range(count):
        words=struct.unpack_from('<12I',data,48+index*48)
        if words[4]+words[5]*8>header[8]:raise ValueError('manifest_reference_bounds')
        rows.append(dict(index=index,type_id=words[0],instance_id=words[1],type_hash=words[2],instance_hash=words[3],
            refs=[struct.unpack_from('<II',data,references+words[4]+8*j) for j in range(words[5])],
            name=text(names,header[10],words[6]),source=text(sources,header[11],words[7]),
            binary_offset=positions[0],binary_size=words[8],relo_offset=positions[1],relo_size=words[9],
            imp_offset=positions[2],imp_size=words[10],flags=words[11]))
        positions=[position+size for position,size in zip(positions,words[8:11])]
    return rows
