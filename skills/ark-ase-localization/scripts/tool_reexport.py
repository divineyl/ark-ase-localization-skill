#!/usr/bin/env python3
"""Optional read-only UE4LocalizationsTool check on a new disposable copy."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path
from ase_localize import (read_json,safe_path,new_directory,digest,write_json,write_bytes,
    canonical_path,preflight_game,read_file,tool_command,is_inside)

def run(args):
    tool,command=tool_command(args.tool); overlay=canonical_path(args.overlay)
    if args.game:
        root,_blobs=preflight_game(args.game)
        if is_inside(root,canonical_path(args.work)):
            raise ValueError('Output must be outside the game tree')
    manifest=read_json(overlay/'manifest.json'); staged=[]
    for entry in manifest['files']:
        source=safe_path(overlay,entry['path']); data=read_file(source)
        if digest(data)!=entry['output_sha256']: raise ValueError('Overlay hash mismatch')
        staged.append((entry,data))
    work=new_directory(args.work,overlay)
    try:
        failures=[]; missing=[]; matched=0
        for entry,data in staged:
            target=safe_path(work,entry['path']); write_bytes(target,data)
            try:
                result=subprocess.run([*command,'export',str(target),'-m2'],cwd=tool.parent,
                                      stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
            except subprocess.TimeoutExpired:
                failures.append({'path':entry['path'],'error':'timeout'}); continue
            text=Path(str(target)+'.txt')
            if result.returncode or not text.exists():
                failures.append({'path':entry['path'],'exit':result.returncode}); continue
            values=[line.split('=',1)[1] for line in text.read_text(encoding='utf-8-sig').splitlines() if '=' in line]
            for edit in entry['edits']:
                expected=edit['translation'].replace('\r\n','<lf>').replace('\n','<lf>').replace('\r','<lf>')
                if expected in values: matched+=1
                else: missing.append({'path':entry['path'],'key':edit['key'],'export_index':edit['export_index']})
            if digest(target.read_bytes())!=entry['output_sha256']: raise ValueError('Exporter modified its copy')
        report={'manifest_sha256':digest((overlay/'manifest.json').read_bytes()),
                'matched_fields':matched,'missing':missing,'failures':failures,'game_tested':False,
                'scope':'Read-only export on copies; value presence corroborates the structural per-location checks.'}
        write_json(work/'reexport_report.json',report)
    except Exception:
        if work.exists() and not (work/'reexport_report.json').exists():
            shutil.rmtree(work,ignore_errors=True)
        raise
    print(json.dumps(report,ensure_ascii=True))
    return 1 if missing or failures else 0

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tool',required=True); p.add_argument('--overlay',required=True); p.add_argument('--work',required=True)
    p.add_argument('--game',help='Preflight this ARK path before copying. Offline checks are not an in-game test.')
    args=p.parse_args(argv)
    try: return run(args)
    except (ValueError,OSError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr); return 1
if __name__=='__main__': raise SystemExit(main())
