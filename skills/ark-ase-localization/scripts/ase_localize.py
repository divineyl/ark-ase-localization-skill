#!/usr/bin/env python3
"""Offline ASE localization workflow. No game installation or network calls."""
import argparse
import collections
import hashlib
import json
from pathlib import Path,PureWindowsPath
import re
import struct
import sys
import zipfile
from ase_assets import Package,patch,unpack_bytes,JSON_FIELDS

def digest(data): return hashlib.sha256(data).hexdigest()
def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write_json(path,value):
    p=Path(path)
    if p.exists(): raise ValueError('Refusing to overwrite: '+str(p))
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def safe_path(root,relative):
    root=Path(root).resolve(); rel=PureWindowsPath(relative)
    if rel.is_absolute() or rel.drive or '..' in rel.parts or not rel.parts:
        raise ValueError('Unsafe relative path: '+relative)
    result=(root/Path(*rel.parts)).resolve()
    if not result.is_relative_to(root): raise ValueError('Path escapes root')
    return result
def new_directory(path,source=None):
    p=Path(path).resolve()
    if p.exists(): raise ValueError('Output already exists: '+str(p))
    if source and p.is_relative_to(Path(source).resolve()): raise ValueError('Output must be outside source tree')
    p.mkdir(parents=True)
    return p
def discover(args):
    if not re.fullmatch(r'[0-9]+',args.id): raise ValueError('Mod ID must contain decimal digits')
    libraries=set(Path(p).expanduser().resolve() for p in args.library)
    # Read Steam registration only; never subscribe, download, or launch Steam.
    if not libraries:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam') as key:
                libraries.add(Path(winreg.QueryValueEx(key,'SteamPath')[0]).resolve())
        except (ImportError,OSError): pass
    for library in list(libraries):
        vdf=library/'steamapps'/'libraryfolders.vdf'
        if vdf.exists():
            for path in re.findall(r'"path"\s+"([^"\r\n]+)"',vdf.read_text(encoding='utf-8-sig')):
                libraries.add(Path(path.replace('\\\\','\\')).resolve())
    found=[]
    for library in sorted(libraries):
        for kind,path in [('installed',library/'steamapps'/'common'/'ARK'/'ShooterGame'/'Content'/'Mods'/args.id),
                          ('workshop-windows',library/'steamapps'/'workshop'/'content'/'346110'/args.id/'WindowsNoEditor')]:
            if path.is_dir(): found.append({'kind':kind,'path':str(path)})
    print(json.dumps({'mod_id':args.id,'candidates':found,'searched_libraries':[str(p) for p in sorted(libraries)]},ensure_ascii=False,indent=2))
def unpack(args):
    source=Path(args.input).resolve(); files=sorted(source.rglob('*.z'))
    if not files: raise ValueError('No .z files under input')
    out=new_directory(args.output,source); manifest=[]
    for f in files:
        rel=f.relative_to(source).with_suffix('')
        if rel.suffix.lower() not in {'.uasset','.umap'}: raise ValueError('Unexpected compressed file: '+str(rel))
        compressed=f.read_bytes(); raw=unpack_bytes(compressed)
        sidecar=Path(str(f)+'.uncompressed_size')
        if sidecar.exists() and int(sidecar.read_text(encoding='ascii').strip())!=len(raw):
            raise ValueError('Sidecar length mismatch: '+str(rel))
        target=safe_path(out,str(rel)); target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(raw)
        manifest.append({'path':rel.as_posix(),'sha256':digest(raw),'compressed_sha256':digest(compressed),'bytes':len(raw)})
    write_json(out/'source_manifest.json',{'files':manifest})
    print(json.dumps({'unpacked_files':len(manifest),'source_modified':False}))
def extract(args):
    source=Path(args.input).resolve(); files=[]; counts=collections.Counter()
    for f in sorted(source.rglob('*.uasset')):
        rel=f.relative_to(source).as_posix(); data=f.read_bytes()
        item={'path':rel,'source_sha256':digest(data),'edits':[]}
        try:
            p=Package(data); rows,opaque=p.records()
            item.update(profile=p.profile,status='parsed',edits=rows,opaque=opaque)
            counts['parsed_files']+=1; counts['typed_strings']+=len(rows)
            counts['display_candidates']+=sum(r['display_candidate'] for r in rows)
        except (ValueError,UnicodeError) as exc:
            item.update(status='unsupported',reason=str(exc)); counts['unsupported_files']+=1
        files.append(item)
    if not files: raise ValueError('No .uasset files under input')
    write_json(args.output,{'schema':1,'allow_language_default':False,'files':files,'counts':dict(counts)})
    print(json.dumps(dict(counts)))

def leaves(value,path=()):
    if isinstance(value,dict):
        for k,v in value.items(): yield from leaves(v,path+(k,))
    elif isinstance(value,list):
        for i,v in enumerate(value): yield from leaves(v,path+(i,))
    else: yield path,value
def text_pairs(edit):
    if edit['kind']=='StrProperty':
        try: before,after=json.loads(edit['source']),json.loads(edit['translation'])
        except (ValueError,TypeError): pass
        else:
            if edit['key']=='MOD_LocalizationString':
                for a,b in zip(before['LStrings'],after['LStrings']):
                    if a.get('ZH')!=b.get('ZH'): yield a.get('EN',''),b.get('ZH','')
            elif edit['key']!='MOD_ClientSettings':
                old=dict(leaves(before))
                for path,value in leaves(after):
                    if isinstance(value,str) and old[path]!=value: yield old[path],value
            return
    yield edit['source'],edit['translation']

def build_overlay(args):
    source=Path(args.input).resolve(); plan=read_json(args.plan)
    if plan.get('schema')!=1: raise ValueError('Unsupported plan schema')
    if type(plan.get('allow_language_default',False)) is not bool: raise ValueError('allow_language_default must be boolean')
    pending=[]; all_pairs=[]; json_occurrences=0
    seen=set()
    for entry in plan['files']:
        changes=[r for r in entry['edits'] if r.get('translation') is not None and r['translation']!=r['source']]
        if not changes: continue
        rel=entry['path']
        if rel in seen or PureWindowsPath(rel).suffix.lower()!='.uasset': raise ValueError('Duplicate/non-asset path')
        seen.add(rel)
        original=safe_path(source,rel).read_bytes()
        if digest(original)!=entry['source_sha256']: raise ValueError('Original SHA-256 mismatch: '+rel)
        result,applied=patch(original,changes,allow_language_default=plan.get('allow_language_default',False))
        inverse=[{**r,'source':r['translation'],'translation':r['source']} for r in applied]
        restored,_=patch(result,inverse,allow_language_default=plan.get('allow_language_default',False))
        if restored!=original: raise ValueError('Inverse is not byte-identical: '+rel)
        for edit in applied:
            pairs=list(text_pairs(edit)); all_pairs.extend(pairs)
            if edit['kind']=='StrProperty' and edit['key'] in JSON_FIELDS: json_occurrences+=len(pairs)
        pending.append((rel,result,{'path':rel,'source_sha256':digest(original),'output_sha256':digest(result),'edits':applied}))
    if not pending: raise ValueError('No changed translations in plan')
    out=new_directory(args.output,source)
    for rel,data,item in pending:
        target=safe_path(out,rel); target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
    manifest={'schema':1,'files':[item for rel,data,item in pending],
              'allow_language_default':plan.get('allow_language_default',False),
              'counts':{'files':len(pending),'edited_properties':sum(len(x[2]['edits']) for x in pending),
                        'translated_text_occurrences':len(all_pairs),'json_text_occurrences':json_occurrences,
                        'unique_translation_pairs':len(set(all_pairs))},
              'inverse_byte_verified':True,'game_tested':False,'installed':False}
    write_json(out/'manifest.json',manifest)
    print(json.dumps(manifest['counts']))
def verify_overlay(source,overlay):
    source,overlay=Path(source).resolve(),Path(overlay).resolve()
    m=read_json(overlay/'manifest.json')
    actual={p.relative_to(overlay).as_posix() for p in overlay.rglob('*.uasset')}
    expected={entry['path'].replace('\\','/') for entry in m['files']}
    if actual!=expected: raise ValueError('Overlay asset set differs from manifest')
    for entry in m['files']:
        original=safe_path(source,entry['path']).read_bytes(); output=safe_path(overlay,entry['path']).read_bytes()
        if digest(original)!=entry['source_sha256'] or digest(output)!=entry['output_sha256']:
            raise ValueError('Hash mismatch: '+entry['path'])
        inverse=[{**e,'source':e['translation'],'translation':e['source']} for e in entry['edits']]
        restored,_=patch(output,inverse,allow_language_default=m.get('allow_language_default',False))
        if restored!=original: raise ValueError('Inverse mismatch: '+entry['path'])
    return m
def verify(args):
    m=verify_overlay(args.source,args.overlay)
    print(json.dumps({'verified_files':len(m['files']),'inverse_byte_verified':True,'game_tested':False}))
def package(args):
    if not re.fullmatch(r'[0-9]+',args.id): raise ValueError('Invalid mod ID')
    m=verify_overlay(args.source,args.overlay); output=Path(args.output)
    independent={'status':'not_run'}
    if args.reexport_report:
        report=read_json(args.reexport_report)
        if report.get('manifest_sha256')!=digest((Path(args.overlay)/'manifest.json').read_bytes()):
            raise ValueError('Independent report belongs to a different overlay manifest')
        expected=sum(len(e['edits']) for e in m['files'])
        if report.get('failures')!=[] or report.get('missing')!=[] or report.get('matched_fields')!=expected:
            raise ValueError('Independent report is incomplete or has failures')
        independent={'status':'passed','matched_fields':expected}
    verification={'source_hashes_verified':True,'overlay_hashes_verified':True,'inverse_byte_verified':True,
                  'independent_reexport':independent,'game_tested':False,'installed':False}
    if output.exists(): raise ValueError('Archive already exists')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for entry in m['files']:
            z.write(safe_path(args.overlay,entry['path']),args.id+'/'+entry['path'].replace('\\','/'))
        z.writestr('manifest.json',json.dumps(m,ensure_ascii=False,indent=2))
        z.writestr('verification.json',json.dumps(verification,ensure_ascii=False,indent=2))
        z.writestr('INSTALL.txt','Overlay patch only. Exit ARK, back up your original mod folder, then merge '+args.id+
                   ' into ShooterGame/Content/Mods. Keep the original .mod descriptor and all other assets. '+
                   'Requires the original mod. Source/output hashes and inverse byte checks passed. '+
                   'Independent re-export: '+independent['status']+'. Game UI has not been tested.\n')
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None: raise ValueError('ZIP CRC check failed')
        for entry in m['files']:
            if digest(z.read(args.id+'/'+entry['path'].replace('\\','/')))!=entry['output_sha256']:
                raise ValueError('ZIP payload hash mismatch')
    print(json.dumps({'zip_verified':True,'sha256':digest(output.read_bytes()),'files':len(m['files'])}))
def main():
    # JSON diagnostics are UTF-8 even when a Windows parent uses a legacy code page.
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'): stream.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__); commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('discover'); p.add_argument('--id',required=True); p.add_argument('--library',action='append',default=[]); p.set_defaults(run=discover)
    for name,fn in [('unpack',unpack),('extract',extract)]:
        p=commands.add_parser(name); p.add_argument('--input',required=True); p.add_argument('--output',required=True); p.set_defaults(run=fn)
    p=commands.add_parser('patch'); p.add_argument('--input',required=True); p.add_argument('--plan',required=True); p.add_argument('--output',required=True); p.set_defaults(run=build_overlay)
    p=commands.add_parser('verify'); p.add_argument('--source',required=True); p.add_argument('--overlay',required=True); p.set_defaults(run=verify)
    p=commands.add_parser('package'); p.add_argument('--source',required=True); p.add_argument('--overlay',required=True); p.add_argument('--id',required=True); p.add_argument('--output',required=True); p.add_argument('--reexport-report'); p.set_defaults(run=package)
    args=parser.parse_args()
    try: args.run(args)
    except (ValueError,OSError,KeyError,TypeError,struct.error) as exc: parser.exit(1,'ERROR: '+str(exc)+'\n')
if __name__=='__main__': main()
