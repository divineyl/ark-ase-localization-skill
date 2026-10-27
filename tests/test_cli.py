import hashlib,json,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
from fixtures import asset,compressed
SCRIPT=Path(__file__).resolve().parents[1]/'skills'/'ark-ase-localization'/'scripts'/'ase_localize.py'
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
