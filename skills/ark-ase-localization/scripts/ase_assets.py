"""Scoped display edits for two observed ASE layouts. Standard library only."""
import json
import re
import struct
import zlib
from ase_layout import Asset,DISPLAY_KEYS,FTEXT_KEYS,fstring,encode_fstring

# Older cooked Nucleus properties, plus single JSON strings written by the public blueprint importer.
# MyMod_LocStrings, permission tags and client/server setting maps are maps, not one JSON string.
JSON_FIELDS={'MOD_LocalizationString','MOD_InfoPage_UIConfig','MOD_ClientSettings',
 'Nucleus_StaticUIConfig','Nucleus_UIConfig','Nucleus_SpawnUIConfig','TestUIConfig',
 'UIConfig_Page','UIConfig_DinoCatalog','UIConfig_ItemsCatalog','UIConfig_DefaultModInfoPage',
 'UIConfig_Settings','UIConfig_Localization','UIConfig_Localization_NotSupported',
 'UIConfig_Logs','UIConfig_Logs_NotSupported','UIConfig_Settings_NotSupported','Languages',
 'N_EditLangDrop_SupportedLanguages','N_Basic_MainUI','N_Basic_MainUI_JsonPlayground',
 'N_Basic_JsonPlayground_Default','N_Basic_MainUI_Encyclopedia','N_Basic_MainUI_InstalledMods',
 'N_Basic_MainUI_AllLogs','N_Basic_Mods_NoCustomInfoPage','MyMod_CustomInfoUI',
 'N_Basic_MainUI_Permissions','Nucleus_MainUI_ServerInfo','Nucleus_MainUI_AllLocalizations',
 'Nucleus_MainUI_AllSurvivors','Nucleus_DefaultServerInfoPage','Nucleus_DisabledServerInfoPage',
 'Nucleus_StructPainter_UIConfig','N_EditColor_ColorPickerUIConfig','Nucleus_Edit_Category_UI',
 'N_BaseWidget_StaticUIConfig','DU_Item_ModalUIConfig','N_BaseWidget_CONST_ErrorWidget',
 'N_BaseWidget_CONST_Modal','N_BaseWidget_CONST_NotifWidget','Nucleus_CONST_TabButtonUIConfig',
 'N_DropDown_DefaultItemWidget','Nucleus_ServerLocalization_Default','MyMod_LocalizationStrings'}
LANG_TABLE_FIELDS={'Nucleus_ServerLocalization_Default','MyMod_LocalizationStrings'}
LANGUAGE_NAME_FIELDS={'Languages','N_EditLangDrop_SupportedLanguages'}
STR_FIELDS=DISPLAY_KEYS|JSON_FIELDS|{'CustomToolTipString','My_PlaceholderModDesc'}
DISPLAY_JSON_LEAVES={'NLText','NLLabel','NLTitle','NLNote','Text','Label','Title','Note','HintText','Placeholder'}
LANG_CODE=re.compile(r'[a-z]{2}(?:-[A-Z]{2})?')
# Whole-value lookup tokens. Underscore keys are the cooked table form; $$Scope$:$KEY is the importer form.
TOKEN_RE=re.compile(r'(?:_[A-Z0-9_]+|\$\$[^$\s]+\$:\$[A-Za-z0-9_-]+)\Z')

def check_placeholders(original,translated):
    if re.findall(r'__\d+__',original)!=re.findall(r'__\d+__',translated):
        raise ValueError('Positional placeholders changed')

def protected_literal(value):
    return isinstance(value,str) and bool(TOKEN_RE.fullmatch(value) or value.startswith(('/Game/','/Script/','/Ark-Nucleus/')))

def reject_protected(before,after):
    if before!=after and (protected_literal(before) or protected_literal(after)):
        raise ValueError('Preserve resource paths and localization tokens')

def is_lang_entry(node):
    if not isinstance(node,dict) or 'en' not in node: return False
    return all(isinstance(key,str) and isinstance(text,str) and LANG_CODE.fullmatch(key) for key,text in node.items())

def validate_lang_table(before,after):
    """Allow only zh to be added, removed or edited. Keep en and every other language."""
    def walk(a,b):
        if is_lang_entry(a) or is_lang_entry(b):
            if not is_lang_entry(a) or not is_lang_entry(b):
                raise ValueError('Localization entry shape changed')
            if (set(a)-set(b))-{'zh'} or (set(b)-set(a))-{'zh'}:
                raise ValueError('Only the zh language may be added or removed')
            for key in set(a)&set(b):
                if key!='zh' and a[key]!=b[key]: raise ValueError('Original language text changed')
            if 'zh' in b:
                if not isinstance(a.get('en'),str): raise ValueError('Missing English reference text')
                check_placeholders(a['en'],b['zh'])
            return
        if not isinstance(a,dict) or not isinstance(b,dict) or set(a)!=set(b):
            raise ValueError('Localization table shape changed')
        for key in a: walk(a[key],b[key])
    walk(before,after)

def text_at(payload,offset=0):
    if offset+9>len(payload) or payload[offset+4]!=0:
        raise ValueError('Only FText Base history 0 is supported')
    namespace,p=fstring(payload,offset+5,len(payload))
    key,p=fstring(payload,p,len(payload))
    source_start=p
    value,p=fstring(payload,p,len(payload))
    return namespace,key,value,source_start,p

def text_array(payload):
    if len(payload)<4: raise ValueError('Truncated FText array')
    count=struct.unpack_from('<i',payload,0)[0]
    if not 0<=count<=10000: raise ValueError('Invalid FText array count')
    records=[]; p=4
    for index in range(count):
        start=p
        namespace,key,value,source_start,p=text_at(payload,p)
        records.append((index,start,source_start,p,namespace,key,value))
    if p!=len(payload): raise ValueError('Trailing FText array data')
    return records

class Package(Asset):
    def records(self):
        """Return typed strings and explicit opaque/unsupported export notices."""
        rows=[]; opaque=[]
        def walk(nodes,export,path=()):
            for index,node in enumerate(nodes):
                loc=path+(index,)
                common={'export_index':export.index,'export_name':export.name,
                        'property_path':list(loc),'key':node['key']}
                kind=node['kind']
                if kind=='StrProperty':
                    rows.append({**common,'kind':kind,'source':node['value'],
                                 'display_candidate':node['key'] in STR_FIELDS})
                elif kind=='TextProperty':
                    try:
                        ns,key,value,start,end=text_at(node['payload'])
                        if end!=len(node['payload']): raise ValueError('Trailing FText data')
                        rows.append({**common,'kind':kind,'source':value,'namespace':ns,
                                     'text_key':key,'display_candidate':node['key'] in FTEXT_KEYS})
                    except ValueError as exc:
                        opaque.append({**common,'reason':str(exc)})
                elif kind=='ArrayProperty' and node['key']=='DisplayNames':
                    try:
                        inner=struct.unpack_from('<i',node['header'],24)[0]
                        if self.names[inner]!='TextProperty': raise ValueError('Not an FText array')
                        for index,start,source_start,end,ns,key,value in text_array(node['payload']):
                            rows.append({**common,'kind':'TextArray','text_index':index,'source':value,
                                         'namespace':ns,'text_key':key,'display_candidate':value!='MAX'})
                    except ValueError as exc: opaque.append({**common,'reason':str(exc)})
                if 'children' in node: walk(node['children'],export,loc)
        for export in self.exports:
            try:
                nodes,_=self.properties(self.data[export.offset:export.offset+export.size])
                walk(nodes,export)
            except (ValueError,UnicodeError,struct.error) as exc:
                opaque.append({'export_index':export.index,'export_name':export.name,'reason':str(exc)})
        return rows,opaque

def locator(row):
    return row['export_index'],tuple(row['property_path']),row.get('text_index')

def validate_json_change(key,old,new,allow_language_default=False):
    """Reject code/binding/permission changes hidden inside display JSON."""
    try: before,after=json.loads(old),json.loads(new)
    except (ValueError,TypeError) as exc: raise ValueError('Invalid JSON') from exc
    if key in LANG_TABLE_FIELDS:
        validate_lang_table(before,after)
        return
    if key=='MOD_LocalizationString':
        if not isinstance(before,dict) or not isinstance(after,dict) or set(before)!=set(after):
            raise ValueError('Localization table shape changed')
        a,b=before.get('LStrings'),after.get('LStrings')
        if not isinstance(a,list) or not isinstance(b,list) or len(a)!=len(b):
            raise ValueError('Preserve localization entries; add missing keys in a separately reviewed change')
        for original,translated in zip(a,b):
            if not isinstance(original,dict) or not isinstance(translated,dict): raise ValueError('Invalid entry')
            if {k:v for k,v in translated.items() if k=='ZH'} and not isinstance(translated['ZH'],str):
                raise ValueError('ZH must be a string')
            if {k:v for k,v in original.items() if k!='ZH'}!={k:v for k,v in translated.items() if k!='ZH'}:
                raise ValueError('Original language/key changed')
            if 'ZH' in translated:
                if not isinstance(original.get('EN'),str): raise ValueError('Missing English reference text')
                check_placeholders(original['EN'],translated['ZH'])
        if {k:v for k,v in before.items() if k!='LStrings'}!={k:v for k,v in after.items() if k!='LStrings'}:
            raise ValueError('Localization metadata changed')
        return
    def compare(a,b,path=(),parent=None):
        if type(a)!=type(b): raise ValueError('JSON type changed: '+str(path))
        if isinstance(a,dict):
            if a.keys()!=b.keys(): raise ValueError('JSON keys changed: '+str(path))
            for k in a: compare(a[k],b[k],path+(k,),a)
        elif isinstance(a,list):
            if len(a)!=len(b): raise ValueError('JSON array length changed')
            for i,(aa,bb) in enumerate(zip(a,b)): compare(aa,bb,path+(i,),a)
        elif a!=b:
            if isinstance(a,str) and isinstance(b,str):
                check_placeholders(a,b); reject_protected(a,b)
            if key=='MOD_ClientSettings':
                if not (allow_language_default and path==('CoreClientSettings','Language') and
                        isinstance(a,str) and isinstance(b,str) and a in {'EN','ZH'} and b in {'EN','ZH'}):
                    raise ValueError('Default language change requires explicit plan flag')
            elif key in LANGUAGE_NAME_FIELDS:
                if path not in {('zh','Name'),('zh','NativeName'),('ZH','Name'),('ZH','NativeName')}:
                    raise ValueError('Only simplified Chinese display names may change')
            elif not (isinstance(a,str) and path[-1] in DISPLAY_JSON_LEAVES):
                if not (isinstance(a,str) and path[-1]=='Name' and isinstance(parent,dict) and 'EnumID' in parent):
                    raise ValueError('Non-display JSON value changed: '+str(path))
    compare(before,after)

def patch(data,edits,allow_language_default=False):
    if not edits: return data,[]
    package=Package(data)
    records,_=package.records(); by_location={locator(r):r for r in records}
    targets={}; applied=[]
    for edit in edits:
        loc=locator(edit)
        if loc in targets: raise ValueError('Duplicate edit locator')
        row=by_location.get(loc)
        if row is None or any(row[k]!=edit[k] for k in ('key','kind','source')):
            raise ValueError('Source/locator mismatch: '+str(loc))
        if not row['display_candidate']: raise ValueError('Not an approved display field: '+row['key'])
        new=edit.get('translation')
        if not isinstance(new,str) or '\0' in new: raise ValueError('Translation must be a NUL-free string')
        if row['kind']=='StrProperty' and row['key'] in JSON_FIELDS:
            validate_json_change(row['key'],row['source'],new,allow_language_default)
        else:
            check_placeholders(row['source'],new); reject_protected(row['source'],new)
        targets[loc]=new; applied.append({**row,'translation':new})
    def rewrite(nodes,tail,export,path=()):
        out=[]
        for index,node in enumerate(nodes):
            prop_path=path+(index,); payload=node['payload']; loc=(export.index,prop_path,None)
            if 'children' in node:
                payload=rewrite(node['children'],node['tail'],export,prop_path)
            elif node['kind']=='ArrayProperty' and node['key']=='DisplayNames':
                matches=[k for k in targets if k[:2]==loc[:2]]
                if matches:
                    parts=[payload[:4]]
                    for i,start,source_start,end,ns,key,value in text_array(payload):
                        target=(export.index,prop_path,i)
                        parts.append(payload[start:source_start]+encode_fstring(targets[target]) if target in targets else payload[start:end])
                    payload=b''.join(parts)
            elif loc in targets:
                new=targets[loc]
                if node['kind']=='StrProperty': payload=encode_fstring(new)
                elif node['kind']=='TextProperty':
                    _,_,_,start,end=text_at(payload); payload=payload[:start]+encode_fstring(new)
            header=bytearray(node['header']); struct.pack_into('<i',header,16,len(payload))
            out.extend((bytes(header),payload))
        return b''.join(out)+tail
    changed={}
    for export in package.exports:
        if not any(loc[0]==export.index for loc in targets): continue
        chunk=data[export.offset:export.offset+export.size]
        nodes,tail=package.properties(chunk); changed[export.index]=rewrite(nodes,tail,export)
    header=bytearray(data[:package.header_size]); parts=[]; cursor=package.header_size; shift=0
    for export in sorted(package.exports,key=lambda e:(e.offset,e.index)):
        parts.append(data[cursor:export.offset])
        new=changed.get(export.index,data[export.offset:export.offset+export.size])
        struct.pack_into('<ii',header,package.export_table+export.index*68+24,len(new),export.offset+shift)
        parts.append(new); shift+=len(new)-export.size; cursor=export.offset+export.size
    parts.append(data[cursor:])
    if package.bulk_offset: struct.pack_into('<q',header,package.profile['bulk'],package.bulk_offset+shift)
    result=bytes(header)+b''.join(parts)
    checked=Package(result); new_records,_=checked.records(); lookup={locator(r):r for r in new_records}
    for e in applied:
        if lookup.get(locator(e),{}).get('source')!=e['translation']: raise ValueError('Reparse failed')
    # Tables other than the permitted export sizes/offsets remain identical.
    if checked.names!=package.names: raise ValueError('Name table changed')
    for before,after in zip(package.exports,checked.exports):
        if before.index not in changed and data[before.offset:before.offset+before.size]!=result[after.offset:after.offset+after.size]:
            raise ValueError('Unrelated export changed')
    return result,applied

def unpack_bytes(data,max_output=1_073_741_824):
    """Decode one observed ARK .z chunk stream, checking every declared size."""
    if len(data)<32: raise ValueError('Truncated compression header')
    magic,chunk_size,compressed_size,total=struct.unpack_from('<4q',data)
    if magic!=0x9e2a83c1: raise ValueError('Unknown compression magic')
    if chunk_size==-1641380927: chunk_size=131072
    if not 0<chunk_size<=max_output or not 0<=total<=max_output or compressed_size<0:
        raise ValueError('Invalid declared compression sizes')
    count=(total+chunk_size-1)//chunk_size
    pos=32+count*16
    if pos>len(data): raise ValueError('Truncated chunk table')
    output=[]; compressed_sum=0
    for i in range(count):
        comp,raw=struct.unpack_from('<qq',data,32+i*16)
        if not 0<comp<=len(data)-pos or not 0<raw<=chunk_size: raise ValueError('Invalid chunk extent')
        try:
            decoder=zlib.decompressobj(); piece=decoder.decompress(data[pos:pos+comp],raw+1)
        except zlib.error as exc: raise ValueError('Invalid zlib stream') from exc
        if len(piece)!=raw or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError('Chunk size/stream mismatch')
        output.append(piece); pos+=comp; compressed_sum+=comp
    if pos!=len(data) or compressed_sum!=compressed_size or sum(map(len,output))!=total:
        raise ValueError('Compression totals mismatch')
    return b''.join(output)
