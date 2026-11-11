import hashlib,json,subprocess,sys,tempfile,unittest,unittest.mock,zipfile
from pathlib import Path
from fixtures import asset,compressed
SCRIPT=Path(__file__).resolve().parents[1]/'skills'/'ark-ase-localization'/'scripts'/'ase_localize.py'
REEXPORT=SCRIPT.with_name('tool_reexport.py')
class CLITests(unittest.TestCase):
    def run_cli(self,*args,ok=True):
        result=subprocess.run([sys.executable,str(SCRIPT),*map(str,args)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode==0,ok,result.stderr)
        return result
    def test_workflow_and_hash_guards(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); cache=root/'cache'; cache.mkdir()
            original=asset(404); (cache/'example.uasset.z').write_bytes(compressed(original))
            self.run_cli('unpack','--input',cache,'--output',root/'original')
            self.run_cli('unpack','--input',cache,'--output',root/'original',ok=False)
            self.run_cli('extract','--input',root/'original','--output',root/'plan.json')
            plan=json.loads((root/'plan.json').read_text(encoding='utf-8'))
            for entry in plan['files']:
                for row in entry['edits']:
                    if row['key']=='ModifierName': row['translation']='寒冷光环'
                    elif row['kind']=='TextProperty': row['translation']='标签：'
                    elif row['key']=='Nucleus_StaticUIConfig':
                        obj=json.loads(row['source']); obj['NLLabel']='生成'
                        row['translation']=json.dumps(obj,ensure_ascii=False)
            (root/'plan.json').write_text(json.dumps(plan,ensure_ascii=False),encoding='utf-8')
            self.run_cli('patch','--input',root/'original','--plan',root/'plan.json','--output',root/'overlay')
            m=json.loads((root/'overlay'/'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(m['counts']['json_text_occurrences'],1)
            self.run_cli('verify','--source',root/'original','--overlay',root/'overlay')
            self.run_cli('package','--source',root/'original','--overlay',root/'overlay','--id','123456789','--output',root/'patch.zip')
            with zipfile.ZipFile(root/'patch.zip') as z:
                self.assertIn('123456789/example.uasset',z.namelist())
                self.assertFalse(any(n.endswith('.mod') for n in z.namelist()))
                verification=json.loads(z.read('verification.json'))
                self.assertEqual(verification['independent_reexport']['status'],'not_run')
                self.assertFalse(verification['game_tested'])
            wrong={'manifest_sha256':'0'*64,'matched_fields':sum(len(e['edits']) for e in m['files']),'missing':[],'failures':[]}
            (root/'wrong-report.json').write_text(json.dumps(wrong),encoding='utf-8')
            self.run_cli('package','--source',root/'original','--overlay',root/'overlay','--id','123456789',
                         '--output',root/'bad-report.zip','--reexport-report',root/'wrong-report.json',ok=False)
            self.assertFalse((root/'bad-report.zip').exists())
            self.assertEqual((root/'original'/'example.uasset').read_bytes(),original)
            (root/'overlay'/'example.uasset').write_bytes(b'corrupt')
            self.run_cli('verify','--source',root/'original','--overlay',root/'overlay',ok=False)
    def test_traversal_and_wrong_source_hash(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); source=root/'source'; source.mkdir(); (source/'example.uasset').write_bytes(asset())
            self.run_cli('extract','--input',source,'--output',root/'plan.json')
            plan=json.loads((root/'plan.json').read_text(encoding='utf-8'))
            row=next(r for r in plan['files'][0]['edits'] if r['key']=='ModifierName'); row['translation']='中文'
            plan['files'][0]['path']='../example.uasset'
            (root/'bad.json').write_text(json.dumps(plan),encoding='utf-8')
            self.run_cli('patch','--input',source,'--plan',root/'bad.json','--output',root/'bad-output',ok=False)
            self.assertFalse((root/'bad-output').exists())
            plan['files'][0]['path']='example.uasset'; plan['files'][0]['source_sha256']='0'*64
            (root/'bad.json').write_text(json.dumps(plan),encoding='utf-8')
            self.run_cli('patch','--input',source,'--plan',root/'bad.json','--output',root/'bad-output',ok=False)
            self.assertFalse((root/'bad-output').exists())
    def test_discover_stdout_is_utf8_for_unicode_paths(self):
        with tempfile.TemporaryDirectory() as d:
            library=Path(d)/'中文库'; cache=library/'steamapps'/'workshop'/'content'/'346110'/'123456789'/'WindowsNoEditor'
            cache.mkdir(parents=True)
            result=self.run_cli('discover','--id','123456789','--library',library)
            found=json.loads(result.stdout)['candidates']
            self.assertEqual(found[0]['path'],str(cache.resolve()))
    def test_discover_library_vdf_ignores_linux_and_bad_ids(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); library=root/'library'; other=root/'other'
            installed=other/'steamapps'/'common'/'ARK'/'ShooterGame'/'Content'/'Mods'/'42'
            installed.mkdir(parents=True)
            (library/'steamapps'/'workshop'/'content'/'346110'/'42'/'LinuxNoEditor').mkdir(parents=True)
            windows=library/'steamapps'/'workshop'/'content'/'346110'/'99'/'WindowsNoEditor'
            windows.mkdir(parents=True)
            (library/'steamapps'/'libraryfolders.vdf').write_text(
                '"libraryfolders"\n{\n"1"\n{\n"path" "'+other.as_posix()+'"\n}\n}\n',encoding='utf-8')
            self.run_cli('discover','--id','MOD','--library',library,ok=False)
            found=json.loads(self.run_cli('discover','--id','42','--library',library).stdout)
            self.assertEqual([item['path'] for item in found['candidates']],[str(installed.resolve())])
            self.assertNotIn('LinuxNoEditor',''.join(item['path'] for item in found['candidates']))
            windows_hit=json.loads(self.run_cli('discover','--id','99','--library',library).stdout)['candidates']
            self.assertEqual(windows_hit[0]['kind'],'workshop-windows')
    def test_unpack_and_extract_report_bad_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); cache=root/'cache'; cache.mkdir()
            (cache/'example.uasset.z').write_bytes(compressed(asset()))
            (cache/'example.uasset.z.uncompressed_size').write_text('1\n',encoding='ascii')
            self.run_cli('unpack','--input',cache,'--output',root/'bad-size',ok=False)
            self.assertFalse((root/'bad-size').exists())
            (cache/'example.uasset.z.uncompressed_size').unlink(); (cache/'notes.txt.z').write_bytes(compressed(b'notes'))
            self.run_cli('unpack','--input',cache,'--output',root/'bad-type',ok=False)
            self.assertFalse((root/'bad-type').exists())
            empty=root/'empty'; empty.mkdir()
            self.run_cli('unpack','--input',empty,'--output',root/'none',ok=False)
            source=root/'source'; source.mkdir(); (source/'ok.uasset').write_bytes(asset()); (source/'bad.uasset').write_bytes(b'not-a-package')
            self.run_cli('extract','--input',source,'--output',root/'plan.json')
            plan=json.loads((root/'plan.json').read_text(encoding='utf-8'))
            self.assertEqual(plan['counts']['parsed_files'],1)
            self.assertEqual(plan['counts']['unsupported_files'],1)
            self.assertEqual(plan['allow_language_default'],False)
    def test_plan_guards_and_reexport_report(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); source=root/'source'; source.mkdir(); (source/'example.uasset').write_bytes(asset(404))
            self.run_cli('extract','--input',source,'--output',root/'plan.json')
            plan=json.loads((root/'plan.json').read_text(encoding='utf-8'))
            plan['schema']=2
            (root/'schema.json').write_text(json.dumps(plan),encoding='utf-8')
            self.run_cli('patch','--input',source,'--plan',root/'schema.json','--output',root/'out',ok=False)
            plan['schema']=1; plan['allow_language_default']='yes'
            (root/'flag.json').write_text(json.dumps(plan),encoding='utf-8')
            self.run_cli('patch','--input',source,'--plan',root/'flag.json','--output',root/'out',ok=False)
            plan['allow_language_default']=False
            for row in plan['files'][0]['edits']:
                if row['key']=='ModifierName': row['translation']=row['source']
                elif row['source']=='Info': row['translation']='信息'
            (root/'plan.json').write_text(json.dumps(plan,ensure_ascii=False),encoding='utf-8')
            self.run_cli('patch','--input',source,'--plan',root/'plan.json','--output',root/'overlay')
            manifest=json.loads((root/'overlay'/'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual([edit['source'] for edit in manifest['files'][0]['edits']],['Info'])
            report={'manifest_sha256':hashlib.sha256((root/'overlay'/'manifest.json').read_bytes()).hexdigest(),
                    'matched_fields':1,'missing':[],'failures':[]}
            (root/'report.json').write_text(json.dumps(report),encoding='utf-8')
            self.run_cli('package','--source',source,'--overlay',root/'overlay','--id','42','--output',root/'patch.zip','--reexport-report',root/'report.json')
            with zipfile.ZipFile(root/'patch.zip') as z:
                self.assertEqual(json.loads(z.read('verification.json'))['independent_reexport']['status'],'passed')
            report['missing']=[{'path':'example.uasset'}]
            (root/'partial.json').write_text(json.dumps(report),encoding='utf-8')
            self.run_cli('package','--source',source,'--overlay',root/'overlay','--id','42','--output',root/'partial.zip','--reexport-report',root/'partial.json',ok=False)
            scripts=str(REEXPORT.parent)
            if scripts not in sys.path: sys.path.insert(0,scripts)
            import tool_reexport
            tool=root/'UE4localizationsTool.exe'; tool.write_bytes(b'MZ-stand-in')
            def reexport(work,text=None,code=0):
                def fake_run(cmd,**kwargs):
                    self.assertEqual(cmd[0],str(tool)); self.assertEqual(cmd[1],'export'); self.assertEqual(cmd[3],'-m2')
                    if text is not None: Path(str(cmd[2])+'.txt').write_text(text,encoding='utf-8')
                    return subprocess.CompletedProcess(cmd,code)
                argv=['tool_reexport.py','--tool',str(tool),'--overlay',str(root/'overlay'),'--work',str(work)]
                with unittest.mock.patch.object(tool_reexport.subprocess,'run',fake_run), unittest.mock.patch.object(sys,'argv',argv):
                    return tool_reexport.main()
            self.assertEqual(reexport(root/'tool-check','k=信息\n'),0)
            self.assertEqual(json.loads((root/'tool-check'/'reexport_report.json').read_text(encoding='utf-8'))['matched_fields'],1)
            self.assertEqual(reexport(root/'tool-miss','k=missing\n'),1)
            self.assertEqual(len(json.loads((root/'tool-miss'/'reexport_report.json').read_text(encoding='utf-8'))['missing']),1)
            self.assertEqual(reexport(root/'tool-fail',code=2),1)
            self.assertEqual(len(json.loads((root/'tool-fail'/'reexport_report.json').read_text(encoding='utf-8'))['failures']),1)
            self.assertEqual((source/'example.uasset').read_bytes(),asset(404))
