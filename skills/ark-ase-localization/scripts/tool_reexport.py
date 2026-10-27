#!/usr/bin/env python3
"""Optional read-only UE4LocalizationsTool check on a new disposable copy."""
import argparse,json,shutil,subprocess
from pathlib import Path
from ase_localize import read_json,safe_path,new_directory,digest,write_json

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tool',required=True); p.add_argument('--overlay',required=True); p.add_argument('--work',required=True)
    args=p.parse_args(); tool=Path(args.tool).resolve(); overlay=Path(args.overlay).resolve()
    if not tool.is_file(): p.error('External exporter not found; it is not bundled')
    manifest=read_json(overlay/'manifest.json'); work=new_directory(args.work,overlay)
    failures=[]; missing=[]; matched=0
    for entry in manifest['files']:
        source=safe_path(overlay,entry['path']); data=source.read_bytes()
        if digest(data)!=entry['output_sha256']: raise ValueError('Overlay hash mismatch')
        target=safe_path(work,entry['path']); target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source,target)
        try:
            result=subprocess.run([str(tool),'export',str(target),'-m2'],cwd=tool.parent,
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
    print(json.dumps(report,ensure_ascii=True))
    return 1 if missing or failures else 0
if __name__=='__main__': raise SystemExit(main())
