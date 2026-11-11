#!/usr/bin/env python3
"""Offline ASE localization workflow. No network calls.

export/install copy files only after path preflight. A finished copy is not an in-game test.
"""
import argparse
import collections
import hashlib
import json
import os
import shutil
from pathlib import Path,PureWindowsPath
import re
import struct
import sys
import zipfile
from ase_assets import Package,patch,unpack_bytes,JSON_FIELDS

# Inputs the ARK LocalizationManager reads before it can export or rebuild archives.
LOCALIZATION_INPUTS=(
    'Tools/LocalizationManager/LocalizationManager.exe',
    'ShooterGame/Content/Localization/Game/en/ShooterGame.archive',
)
_SHORT_NAME=re.compile(
    r'^(?P<stem>[^\\/:*?"<>|. ]{1,6})~(?P<num>[1-9]\d?)(?P<ext>\.[^\\/:*?"<>|. ]{1,3})?$',
    re.IGNORECASE)

def digest(data): return hashlib.sha256(data).hexdigest()
def read_file(path):
    try:
        with open(path,'rb') as handle: return handle.read()
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise ValueError('Unreadable file: '+str(path)) from exc
def read_json(path):
    try: return json.loads(read_file(path).decode('utf-8-sig'))
    except UnicodeError as exc:
        raise ValueError('Unreadable file: '+str(path)) from exc
def write_bytes(path,data):
    target=Path(path); target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
def write_json(path,value):
    p=Path(path)
    if p.exists(): raise ValueError('Refusing to overwrite: '+str(p))
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def _strip_extended(text):
    if text.startswith('\\\\?\\UNC\\'): return '\\\\'+text[8:]
    if text.startswith('\\\\?\\'): return text[4:]
    return text
def logical_parts(path):
    """Split a Windows or Linux path. Both separators count, and .. is folded."""
    text=_strip_extended(os.path.expanduser(str(path))).replace('\\','/')
    drive=''; unc=text.startswith('//')
    if not unc and len(text)>=2 and text[1]==':' and text[0].isalpha():
        drive,text=text[:2],text[2:]
    absolute=unc or text.startswith('/') or bool(drive)
    stack=[]
    for part in text.split('/'):
        if part in ('','.'): continue
        if part=='..':
            if stack: stack.pop()
            elif not absolute: stack.append('..')
        else: stack.append(part)
    return drive,absolute,unc,stack
def _scrub83(text):
    return ''.join(ch for ch in text if ch not in ' .\\/:*?"<>|').upper()
def short_name(name,index=1):
    """Approximate the 8.3 alias Windows stores beside one long file name."""
    base,ext=os.path.splitext(name)
    base_body,ext_body=_scrub83(base),(_scrub83(ext[1:])[:3] if ext.startswith('.') else '')
    needs_tilde=(len(base_body)>8 or len(ext_body)>3 or _scrub83(base)!=base.upper()
                 or ' ' in name or '.' in base)
    short_base=(base_body[:6]+'~'+str(index)) if needs_tilde else base_body[:8]
    if not short_base: short_base='~'+str(index)
    return short_base+(('.'+ext_body) if ext_body else '')
def match_short_name(names,component):
    """Return the only long name whose 8.3 alias is component, or None when it is ambiguous."""
    match=_SHORT_NAME.match(component)
    if not match: return None
    expected=(match.group('stem')+'~'+match.group('num')+(match.group('ext') or '')).upper()
    num=int(match.group('num'))
    found=[]
    for name in names:
        if short_name(name,num).upper()==expected and name not in found: found.append(name)
    return found[0] if len(found)==1 else None
def expand_short_component(parent,component):
    if not _SHORT_NAME.match(component): return component
    parent=Path(parent)
    if not parent.is_dir(): return component
    direct=parent/component
    try:
        if direct.exists():
            resolved_name=direct.resolve().name
            # Windows resolve() already expands RUNNER~1 to runneradmin when the alias exists.
            if resolved_name!=component and (parent/resolved_name).exists(): return resolved_name
    except OSError:
        return component
    try: names=[child.name for child in parent.iterdir()]
    except OSError: return component
    return match_short_name(names,component) or component
def _drop_extended(path):
    text=str(path)
    if text.startswith('\\\\?\\UNC\\'): return Path('\\\\'+text[8:])
    if text.startswith('\\\\?\\'): return Path(text[4:])
    return path
def canonical_path(path):
    """Absolute local path with short names expanded. Drive and UNC text stay lexical off Windows."""
    drive,absolute,unc,parts=logical_parts(path)
    if os.name!='nt' and (unc or drive):
        prefix='//'+'/'.join(parts) if unc else drive+'/'+'/'.join(parts)
        return Path(prefix)
    if unc and os.name=='nt':
        if len(parts)<2: return Path('\\\\'+'\\'.join(parts))
        built=Path('\\\\%s\\%s\\'%(parts[0],parts[1])); parts=parts[2:]
    elif drive and os.name=='nt': built=Path(drive+'\\')
    elif absolute: built=Path(os.sep)
    else: built=Path.cwd()
    for part in parts:
        built=built/expand_short_component(built,part)
        # Resolve each existing prefix so a symlink or 8.3 parent still contains its children.
        try:
            if built.exists(): built=_drop_extended(built.resolve())
        except OSError: pass
    return built
def path_key(path):
    drive,_absolute,unc,parts=logical_parts(path)
    # On Windows a drive path such as C:\\Users\\RUNNER~1 must be resolved before comparison.
    if os.name!='nt' and (drive or unc):
        text=('//' if unc else drive+'/')+'/'.join(parts)
    else:
        text=str(canonical_path(path)).replace('\\','/')
    return os.path.normcase(text) if os.name=='nt' else text
def same_path(a,b): return path_key(a)==path_key(b)
def is_inside(parent,child):
    parent,child=canonical_path(parent),canonical_path(child)
    if os.name=='nt':
        parent,child=Path(os.path.normcase(str(parent))),Path(os.path.normcase(str(child)))
    return child==parent or child.is_relative_to(parent)
def safe_path(root,relative):
    root=canonical_path(root); rel=PureWindowsPath(relative)
    if rel.is_absolute() or rel.drive or '..' in rel.parts or not rel.parts:
        raise ValueError('Unsafe relative path: '+str(relative))
    result=canonical_path(root.joinpath(*rel.parts))
    if not is_inside(root,result): raise ValueError('Path escapes root')
    return result
def new_directory(path,source=None):
    p=canonical_path(path)
    if p.exists(): raise ValueError('Output already exists: '+str(p))
    if source and is_inside(source,p): raise ValueError('Output must be outside source tree')
    p.mkdir(parents=True)
    return p
def preflight_game(game):
    """Read the game tree before any export or install write. Fail closed on a bad path."""
    origin=canonical_path(game)
    if not origin.exists(): raise ValueError('Bad game path: does not exist: '+str(origin))
    if not origin.is_dir(): raise ValueError('Bad game path: not a directory: '+str(origin))
    if any(part.lower()=='linuxnoeditor' for part in origin.parts):
        raise ValueError('Bad game path: Linux cook is not a Windows game target: '+str(origin))
    try: next(origin.iterdir(), None)
    except OSError as exc:
        raise ValueError('Bad game path: unreadable directory: '+str(origin)) from exc
    root=None; cursor=origin; seen=set()
    while cursor not in seen:
        seen.add(cursor)
        shooter=cursor/'ShooterGame'
        if shooter.is_dir():
            if not is_inside(cursor,shooter):
                raise ValueError('Bad game path: resolved path escapes the game tree: '+str(canonical_path(shooter)))
            root=canonical_path(cursor); break
        if cursor==cursor.parent: break
        cursor=cursor.parent
    if root is None: raise ValueError('Bad game path: ShooterGame directory not found under '+str(origin))
    if not is_inside(root,origin):
        raise ValueError('Bad game path: resolved path escapes the game tree: '+str(origin))
    missing=[]; blobs=[]
    for rel in LOCALIZATION_INPUTS:
        path=canonical_path(root.joinpath(*rel.split('/')))
        if not is_inside(root,path):
            raise ValueError('Bad game path: resolved path escapes the game tree: '+str(path))
        if not path.is_file():
            missing.append(rel); continue
        blobs.append((rel,path,read_file(path)))
    if missing: raise ValueError('Missing LocalizationManager inputs: '+', '.join(missing))
    return root,blobs
def _discard_output(path):
    if path.exists(): shutil.rmtree(path,ignore_errors=True)
def export_inputs(args):
    root,blobs=preflight_game(args.game)
    output=canonical_path(args.output)
    if is_inside(root,output): raise ValueError('Output must be outside the game tree')
    out=new_directory(output)
    try:
        files=[]
        for rel,_path,data in blobs:
            write_bytes(safe_path(out,rel),data)
            files.append({'path':rel,'sha256':digest(data)})
        write_json(out/'export_manifest.json',{
            'schema':1,'ark_root':str(root),'game':str(canonical_path(args.game)),'files':files,
            'game_tested':False,'installed':False,
            'note':'Offline copy of LocalizationManager inputs. Not an in-game test.'})
    except Exception as exc:
        _discard_output(out)
        raise ValueError('Export failed before completion; no partial output kept: '+str(exc)) from exc
    print(json.dumps({'copied_files':len(blobs),'game_tested':False}))
def _restore_install(written,mods,mods_existed,backup_path):
    for dest,previous in reversed(written):
        if previous is None:
            if dest.is_file() or dest.is_symlink(): dest.unlink()
        else: write_bytes(dest,previous)
    if not mods_existed and mods.exists(): shutil.rmtree(mods)
    if backup_path.exists(): shutil.rmtree(backup_path)
def install_overlay(args):
    root,_blobs=preflight_game(args.game)
    if not re.fullmatch(r'[0-9]+',args.id): raise ValueError('Invalid mod ID')
    overlay=canonical_path(args.overlay)
    manifest=read_json(overlay/'manifest.json')
    if manifest.get('schema')!=1: raise ValueError('Unsupported plan schema')
    if not manifest.get('files'): raise ValueError('No files to install')
    mods=canonical_path(root/'ShooterGame'/'Content'/'Mods'/args.id)
    if not is_inside(root,mods):
        raise ValueError('Bad game path: mod directory escapes the game tree: '+str(mods))
    backup_path=canonical_path(args.backup)
    if backup_path.exists(): raise ValueError('Output already exists: '+str(backup_path))
    if is_inside(root,backup_path) or is_inside(overlay,backup_path):
        raise ValueError('Backup must be outside the game and the overlay')
    planned=[]
    for entry in manifest['files']:
        rel=entry['path']
        data=read_file(safe_path(overlay,rel))
        if digest(data)!=entry['output_sha256']: raise ValueError('Hash mismatch: '+rel)
        dest=safe_path(mods,rel)
        if dest.exists():
            if not dest.is_file(): raise ValueError('Unreadable file: '+str(dest))
            current=read_file(dest)
            if digest(current) not in {entry['source_sha256'],entry['output_sha256']}:
                raise ValueError('Refusing unknown installed version: '+rel)
            previous=current
        else: previous=None
        planned.append((rel,data,dest,previous))
    mods_existed=mods.exists()
    try: backup_path.mkdir(parents=True)
    except OSError as exc:
        raise ValueError('Install failed before completion; game files were not changed: '+str(exc)) from exc
    try:
        backed=[]
        for rel,_data,_dest,previous in planned:
            if previous is not None: write_bytes(safe_path(backup_path,rel),previous)
            backed.append({'path':rel.replace('\\','/'),'action':'replaced' if previous is not None else 'created',
                           'sha256':digest(previous) if previous is not None else None})
        write_json(backup_path/'backup_manifest.json',{'mod_id':args.id,'files':backed,'game_tested':False,
            'note':'Backup taken before an offline copy. Not an in-game test.'})
    except Exception as exc:
        _discard_output(backup_path)
        raise ValueError('Install failed before completion; game files were not changed: '+str(exc)) from exc
    written=[]
    try:
        for rel,data,dest,previous in planned:
            write_bytes(dest,data); written.append((dest,previous))
            if digest(read_file(dest))!=digest(data): raise ValueError('Output hash mismatch: '+rel)
    except Exception as exc:
        try: _restore_install(written,mods,mods_existed,backup_path)
        except Exception as restore_exc:
            raise ValueError('Install failed and restore failed; backup kept at '+str(backup_path)+': '+str(restore_exc)) from exc
        raise ValueError('Install failed before completion; game files restored: '+str(exc)) from exc
    print(json.dumps({'copied_files':len(planned),'backup':str(backup_path),'game_tested':False}))
def tool_command(tool):
    """Start an external exporter. Windows does not honor a Python shebang."""
    tool=canonical_path(tool)
    if not tool.is_file(): raise ValueError('External exporter not found; it is not bundled')
    head=read_file(tool)
    first=head.splitlines()[0].lower() if head.startswith(b'#!') else b''
    if tool.suffix.lower()=='.py' or b'python' in first:
        return tool,[sys.executable,str(tool)]
    return tool,[str(tool)]
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
    p=commands.add_parser('export',help='Copy LocalizationManager inputs after path preflight. Not an in-game test.')
    p.add_argument('--game',required=True); p.add_argument('--output',required=True); p.set_defaults(run=export_inputs)
    p=commands.add_parser('install',help='Copy an overlay into Mods after preflight and a backup. Not an in-game test.')
    p.add_argument('--game',required=True); p.add_argument('--overlay',required=True); p.add_argument('--id',required=True); p.add_argument('--backup',required=True); p.set_defaults(run=install_overlay)
    args=parser.parse_args()
    try: args.run(args)
    except (ValueError,OSError,KeyError,TypeError,struct.error) as exc: parser.exit(1,'ERROR: '+str(exc)+'\n')
if __name__=='__main__': main()
