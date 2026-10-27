"""Generate tiny, synthetic package-shaped fixtures; no game content."""
import struct,zlib

MAGIC=bytes.fromhex('c1832a9e')
def fs(s):
    try:
        raw=s.encode('ascii')+b'\0'; return struct.pack('<i',len(raw))+raw
    except UnicodeEncodeError:
        raw=s.encode('utf-16-le')+b'\0\0'; return struct.pack('<i',-len(raw)//2)+raw

def asset(version=402):
    licensee,no,bulk=(7,163,147) if version==402 else (10,171,155)
    names=['None','StrProperty','StructProperty','TextProperty','ArrayProperty',
      'BuffDescription','StatusValueModifierDescription','ModifierName','ModifierDescription',
      'Text','DisplayNames','Default__Example_C','Widget_A','Widget_B','Enum_A',
      'Nucleus_StaticUIConfig','DinoNameTag']
    def fn(s): return struct.pack('<ii',names.index(s),0)
    def tag(name,kind,payload,extra=b''):
        return fn(name)+fn(kind)+struct.pack('<ii',len(payload),0)+extra+payload
    def text(s): return struct.pack('<IB',0,0)+fs('synthetic-namespace')+fs('stable-key')+fs(s)
    buff=tag('ModifierName','StrProperty',fs('Cold Aura'))+tag('ModifierDescription','StrProperty',fs('Cooling you down.'))+fn('None')
    config='{"NLLabel":"Spawn","EventUID":"Nucleus/Spawn","BindValue":"Health","Min":0}'
    chunks=[tag('BuffDescription','StructProperty',buff,fn('StatusValueModifierDescription'))+
            tag('DinoNameTag','StrProperty',fs('ExampleInternalTag'))+
            tag('Nucleus_StaticUIConfig','StrProperty',fs(config))+fn('None')+b'opaque-tail',
            tag('Text','TextProperty',text('Label:'))+fn('None'),
            tag('Text','TextProperty',text('LABEL:'))+fn('None'),
            tag('DisplayNames','ArrayProperty',struct.pack('<i',2)+text('Info')+text('MAX'),fn('TextProperty'))+fn('None')]
    nameblob=b''.join(map(fs,names)); io=no+len(nameblob); eo=io+28; dep=eo+len(chunks)*68; hs=dep+len(chunks)*4
    header=bytearray(hs)
    header[:24]=struct.pack('<Iiiiii',0x9e2a83c1,-3,864,version,licensee,0)
    struct.pack_into('<i',header,24,hs); header[28:37]=fs('None')
    struct.pack_into('<7i',header,41,len(names),no,len(chunks),eo,1,io,dep)
    header[no:io]=nameblob
    cursor=hs
    for i,chunk in enumerate(chunks):
        rec=eo+i*68; struct.pack_into('<i',header,rec,-1)
        struct.pack_into('<i',header,rec+12,names.index(['Default__Example_C','Widget_A','Widget_B','Enum_A'][i]))
        struct.pack_into('<ii',header,rec+24,len(chunk),cursor); cursor+=len(chunk)
    struct.pack_into('<q',header,bulk,cursor)
    return bytes(header)+b''.join(chunks)+MAGIC

def compressed(data,chunk_size=128):
    parts=[data[i:i+chunk_size] for i in range(0,len(data),chunk_size)]
    blobs=[zlib.compress(p) for p in parts]
    return struct.pack('<4q',0x9e2a83c1,chunk_size,sum(map(len,blobs)),len(data))+b''.join(struct.pack('<qq',len(b),len(p)) for b,p in zip(blobs,parts))+b''.join(blobs)
