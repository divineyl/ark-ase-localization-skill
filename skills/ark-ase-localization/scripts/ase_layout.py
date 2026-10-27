"""Read the two observed ASE package layouts; unknown layouts are rejected.

Name maps, imports, class references, bytecode and unrelated export data remain
byte-identical. This deliberately supports only the exact inspected format.
"""
from dataclasses import dataclass
import struct

PREFIX=bytes.fromhex('c1832a9efdffffff60030000920100000700000000000000')
DISPLAY_KEYS=frozenset({'ModifierName','ModifierDescription','HUDMessage',
    'DescriptiveName','DinoDescriptiveName','DescriptiveNameBase','ItemDescription',
    'ModName','ModDescription','InventoryNameOverride','RemoteInventoryDescriptionString',
    'ActivateContainerString','DeactivateContainerString','OpenSceneActionName',
    'DisabledOpenSceneActionName','Text','ButtonText','ToolTipText','TooltipText'})

def fstring(data, offset, end):
    if offset+4>end: raise ValueError('Truncated FString length')
    count=struct.unpack_from('<i',data,offset)[0]
    width=1 if count>=0 else 2
    size=abs(count)*width
    stop=offset+4+size
    if stop>end or size>16_000_000: raise ValueError('Invalid FString extent')
    if not count: return '',stop
    raw=data[offset+4:stop]
    if raw[-width:]!=b'\0'*width: raise ValueError('Missing FString terminator')
    return raw[:-width].decode('cp1252' if width==1 else 'utf-16-le'),stop

def encode_fstring(value):
    if '\0' in value: raise ValueError('Embedded NUL in translation')
    try:
        raw=value.encode('ascii')+b'\0'
        return struct.pack('<i',len(raw))+raw
    except UnicodeEncodeError:
        raw=value.encode('utf-16-le')+b'\0\0'
        return struct.pack('<i',-(len(raw)//2))+raw

@dataclass(frozen=True)
class Export:
    index:int
    name:str
    offset:int
    size:int

PROFILES={
    PREFIX: {'version':402,'licensee':7,'names':163,'bulk':147},
    bytes.fromhex('c1832a9efdffffff60030000940100000a00000000000000'):
        {'version':404,'licensee':10,'names':171,'bulk':155},
}

class Asset:
    def __init__(self,data):
        self.data=data
        profile=PROFILES.get(data[:24])
        self.profile=profile
        if len(data)<167 or profile is None:
            raise ValueError('Unsupported package version; require observed ASE 402/7 or 404/10')
        self.header_size=struct.unpack_from('<i',data,24)[0]
        folder,pos=fstring(data,28,len(data))
        if folder!='None' or pos!=37: raise ValueError('Unsupported package folder layout')
        nc,no,ec,eo,ic,io,dep=struct.unpack_from('<7i',data,41)
        if no!=profile['names'] or min(nc,ec,ic)<0 or eo!=io+ic*28 or dep!=eo+ec*68:
            raise ValueError('Unsupported name/import/export table layout')
        if not profile['names']<=io<=eo<=dep<=self.header_size<=len(data)-4:
            raise ValueError('Invalid package boundaries')
        if data[-4:]!=bytes.fromhex('c1832a9e'): raise ValueError('Missing package footer')
        self.names=[]
        p=no
        for _ in range(nc):
            name,p=fstring(data,p,io)
            self.names.append(name)
        if p!=io: raise ValueError('Name table length mismatch')
        self.export_table=eo
        self.bulk_offset=struct.unpack_from('<q',data,profile['bulk'])[0]
        if self.bulk_offset not in (0,len(data)-4):
            raise ValueError('Unsupported external/bulk payload layout')
        self.exports=[]
        for i in range(ec):
            rec=eo+i*68
            ni=struct.unpack_from('<i',data,rec+12)[0]
            size,start=struct.unpack_from('<ii',data,rec+24)
            if not 0<=ni<len(self.names) or size<0 or not self.header_size<=start<=start+size<=len(data)-4:
                raise ValueError('Invalid export range')
            self.exports.append(Export(i,self.names[ni],start,size))
        previous=self.header_size
        for e in sorted(self.exports,key=lambda x:(x.offset,x.index)):
            if e.offset<previous: raise ValueError('Overlapping exports')
            previous=e.offset+e.size

    def properties(self,chunk,depth=0):
        if depth>8: raise ValueError('Property nesting exceeds limit')
        p=0
        nodes=[]
        while p<len(chunk):
            if p+8>len(chunk): raise ValueError('Truncated property name')
            ni,num=struct.unpack_from('<ii',chunk,p)
            if not 0<=ni<len(self.names): raise ValueError('Invalid property name index')
            key=self.names[ni]
            if key=='None': return nodes,chunk[p:]
            if p+24>len(chunk): raise ValueError('Truncated property header')
            ti,tn,size,array_index=struct.unpack_from('<4i',chunk,p+8)
            if not 0<=ti<len(self.names): raise ValueError('Invalid property type index')
            kind=self.names[ti]
            extra={'BoolProperty':1,'ByteProperty':8,'StructProperty':8,'ArrayProperty':8}.get(kind,0)
            start=p+24+extra
            end=start+size
            if not kind.endswith('Property') or size<0 or end>len(chunk):
                raise ValueError('Invalid property boundaries: '+key)
            node={'key':key,'kind':kind,'header':chunk[p:start],'payload':chunk[start:end],
                'array_index':array_index}
            if kind=='StrProperty':
                value,stop=fstring(chunk,start,end)
                if stop!=end: raise ValueError('FString/property size mismatch: '+key)
                node['value']=value
            if kind=='StructProperty':
                si,sn=struct.unpack_from('<ii',chunk,p+24)
                if not 0<=si<len(self.names): raise ValueError('Invalid struct name')
                node['struct_type']=self.names[si]
                if key=='BuffDescription' and node['struct_type']=='StatusValueModifierDescription':
                    node['children'],node['tail']=self.properties(node['payload'],depth+1)
            nodes.append(node)
            p=end
        raise ValueError('Property list lacks None terminator')

