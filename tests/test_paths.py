"""Path normalization and preflight. Samples are synthetic directories, not game files."""
import argparse,contextlib,hashlib,io,json,os,subprocess,sys,tempfile,unittest,unittest.mock
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills'/'ark-ase-localization'/'scripts'))
import ase_localize

class PathNormalizationTests(unittest.TestCase):
    def test_short_name_matches_runneradmin(self):
        self.assertEqual(ase_localize.short_name('runneradmin'),'RUNNER~1')
        self.assertEqual(ase_localize.match_short_name(['runneradmin'],'RUNNER~1'),'runneradmin')
        self.assertEqual(ase_localize.match_short_name(['runneradmin'],'runner~1'),'runneradmin')
        self.assertIsNone(ase_localize.match_short_name(['runneradmin','runnerbeta'],'RUNNER~1'))
        self.assertEqual(ase_localize.match_short_name(['KEEP~1'],'KEEP~1'),'KEEP~1')
    def test_separators_dotdot_and_extended_prefix(self):
        self.assertTrue(ase_localize.same_path('folder/file.txt','folder\\file.txt'))
        self.assertTrue(ase_localize.same_path('a/b/../c','a/c'))
        self.assertTrue(ase_localize.same_path(r'\\?\C:\Games\ARK',r'C:\Games\ARK'))
        self.assertTrue(ase_localize.same_path(r'\\?\C:\Games\ARK','C:/Games/ARK'))
    def test_short_directory_resolves_before_comparison(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); sandbox=root/'runneradmin'/'sandbox'; sandbox.mkdir(parents=True)
            (sandbox/'example.uasset').write_bytes(b'data')
            (sandbox/'sub').mkdir(); (sandbox/'sub'/'example.uasset').write_bytes(b'nested')
            short=root/'RUNNER~1'/'sandbox'
            self.assertTrue(ase_localize.same_path(short,sandbox))
            self.assertNotEqual(str(short),str(sandbox))
            found=ase_localize.safe_path(short,'example.uasset')
            self.assertEqual(found.read_bytes(),b'data')
            self.assertTrue(ase_localize.same_path(found,sandbox/'example.uasset'))
            nested=ase_localize.safe_path(sandbox,r'sub\example.uasset')
            self.assertEqual(nested.read_bytes(),b'nested')
            source=root/'runneradmin'/'cache'; source.mkdir()
            with self.assertRaises(ValueError):
                ase_localize.new_directory(root/'RUNNER~1'/'cache'/'out',source)
            self.assertFalse((source/'out').exists())
    def test_literal_short_directory_is_kept(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'KEEP~1'; root.mkdir()
            self.assertTrue(ase_localize.same_path(root,Path(d)/'KEEP~1'))
            self.assertEqual(ase_localize.canonical_path(root).name,'KEEP~1')
    def test_safe_path_rejects_parent_and_symlink_escape(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); sandbox=root/'sandbox'; sandbox.mkdir(); outside=root/'outside'; outside.mkdir()
            secret=outside/'secret.txt'; secret.write_bytes(b'secret')
            (sandbox/'link').symlink_to(secret)
            with self.assertRaises(ValueError) as escaped:
                ase_localize.safe_path(sandbox,'link')
            self.assertIn('escapes',str(escaped.exception))
            with self.assertRaises(ValueError) as parent:
                ase_localize.safe_path(sandbox,'../outside/secret.txt')
            self.assertIn('Unsafe',str(parent.exception))
            self.assertFalse((sandbox/'secret.txt').exists())
    @unittest.skipIf(os.name=='nt','Windows may bind one 8.3 alias to a single long name')
    def test_ambiguous_short_names_are_not_guessed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'runneradmin').mkdir(); (root/'runnerbeta').mkdir()
            self.assertFalse(ase_localize.same_path(root/'RUNNER~1',root/'runneradmin'))
            self.assertFalse(ase_localize.canonical_path(root/'RUNNER~1').exists())

SCRIPT=Path(__file__).resolve().parents[1]/'skills'/'ark-ase-localization'/'scripts'/'ase_localize.py'

def make_game(root):
    root=Path(root)
    exe=root/'Tools'/'LocalizationManager'/'LocalizationManager.exe'
    archive=root/'ShooterGame'/'Content'/'Localization'/'Game'/'en'/'ShooterGame.archive'
    exe.parent.mkdir(parents=True); archive.parent.mkdir(parents=True)
    (root/'ShooterGame'/'Content'/'Mods').mkdir(parents=True)
    exe.write_bytes(b'MZ-localization-manager'); archive.write_bytes(b'archive-bytes')
    return root

def make_overlay(path,files):
    path=Path(path); path.mkdir(parents=True)
    manifest={'schema':1,'files':[]}
    for rel,source,output in files:
        target=path/rel; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(output)
        manifest['files'].append({'path':rel,'source_sha256':hashlib.sha256(source).hexdigest(),
                                   'output_sha256':hashlib.sha256(output).hexdigest(),'edits':[]})
    (path/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    return path

class PreflightTests(unittest.TestCase):
    def run_cli(self,*args,ok=True):
        result=subprocess.run([sys.executable,str(SCRIPT),*map(str,args)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode==0,ok,result.stderr or result.stdout)
        return result
    def test_export_rejects_bad_paths_without_writing(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); game=make_game(root/'ARK'); out=root/'out'
            missing=root/'only-shooter'; (missing/'ShooterGame').mkdir(parents=True); nowhere=root/'nowhere'
            self.run_cli('export','--game',nowhere,'--output',out,ok=False)
            self.assertFalse(out.exists())
            result=self.run_cli('export','--game',missing,'--output',out,ok=False)
            self.assertIn('Missing LocalizationManager inputs',result.stderr)
            self.assertIn('LocalizationManager.exe',result.stderr)
            self.assertFalse(out.exists())
            archive=game/'ShooterGame'/'Content'/'Localization'/'Game'/'en'/'ShooterGame.archive'
            archive.unlink()
            result=self.run_cli('export','--game',game,'--output',out,ok=False)
            self.assertIn('ShooterGame.archive',result.stderr)
            self.assertFalse(out.exists())
            archive.write_bytes(b'archive-bytes')
            linux=game/'LinuxNoEditor'; linux.mkdir()
            result=self.run_cli('export','--game',linux,'--output',out,ok=False)
            self.assertIn('Bad game path',result.stderr)
            self.assertIn('Linux',result.stderr)
            self.assertFalse(out.exists())
            game_file=root/'not-a-dir'; game_file.write_text('x',encoding='utf-8')
            result=self.run_cli('export','--game',game_file,'--output',out,ok=False)
            self.assertIn('not a directory',result.stderr)
            inside=game/'ShooterGame'/'dump'
            self.run_cli('export','--game',game,'--output',inside,ok=False)
            self.assertFalse(inside.exists())
            marker=root/'existing'; marker.mkdir(); (marker/'keep.txt').write_text('keep',encoding='utf-8')
            self.run_cli('export','--game',game,'--output',marker,ok=False)
            self.assertEqual((marker/'keep.txt').read_text(encoding='utf-8'),'keep')
    def test_export_unreadable_input_and_partial_write(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); game=make_game(root/'ARK'); exe=game/'Tools'/'LocalizationManager'/'LocalizationManager.exe'
            before=exe.read_bytes(); out=root/'out'
            real_open=open
            def locked(path,*args,**kwargs):
                # Resolved paths can differ by 8.3 name or case, so match the file name.
                if Path(path).name.lower()=='localizationmanager.exe': raise PermissionError('denied')
                return real_open(path,*args,**kwargs)
            with unittest.mock.patch('builtins.open',locked):
                with self.assertRaises(ValueError) as caught:
                    ase_localize.export_inputs(argparse.Namespace(game=str(game),output=str(out)))
            self.assertIn('Unreadable file',str(caught.exception))
            self.assertFalse(out.exists()); self.assertEqual(exe.read_bytes(),before)
            real_write=ase_localize.write_bytes
            def fail_archive(path,data):
                if Path(path).name=='ShooterGame.archive': raise OSError('disk full')
                return real_write(path,data)
            with unittest.mock.patch.object(ase_localize,'write_bytes',fail_archive):
                with self.assertRaises(ValueError) as partial:
                    ase_localize.export_inputs(argparse.Namespace(game=str(game),output=str(out)))
            self.assertIn('no partial output kept',str(partial.exception))
            self.assertFalse(out.exists()); self.assertEqual(exe.read_bytes(),before)
    def test_export_accepts_short_and_backslash_paths(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); game=make_game(root/'runneradmin'/'ARK'); out=root/'exported'
            outside=root/'outside'; outside.mkdir(); secret=outside/'secret.txt'; secret.write_bytes(b'secret')
            archive=game/'ShooterGame'/'Content'/'Localization'/'Game'/'en'/'ShooterGame.archive'
            archive.unlink(); archive.symlink_to(secret)
            result=self.run_cli('export','--game',root/'RUNNER~1'/'ARK','--output',out,ok=False)
            self.assertIn('escapes',result.stderr); self.assertFalse(out.exists()); self.assertEqual(secret.read_bytes(),b'secret')
            archive.unlink(); archive.write_bytes(b'archive-bytes')
            windows=str(root/'RUNNER~1'/'ARK').replace('/','\\')
            result=self.run_cli('export','--game',windows,'--output',out)
            report=json.loads(result.stdout)
            self.assertEqual(report['copied_files'],2); self.assertFalse(report['game_tested'])
            manifest=json.loads((out/'export_manifest.json').read_text(encoding='utf-8'))
            self.assertFalse(manifest['game_tested']); self.assertFalse(manifest['installed'])
            self.assertIn('Not an in-game test',manifest['note'])
            self.assertTrue(ase_localize.same_path(manifest['game'],game))
            self.assertTrue(ase_localize.same_path(manifest['ark_root'],game))
            copied=out/'ShooterGame'/'Content'/'Localization'/'Game'/'en'/'ShooterGame.archive'
            self.assertEqual(copied.read_bytes(),archive.read_bytes())
            self.assertEqual(archive.read_bytes(),b'archive-bytes')
    def test_install_refuses_bad_inputs_without_a_backup(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); game=make_game(root/'ARK'); overlay=make_overlay(root/'overlay',[('example.uasset',b'original',b'patched')])
            backup=root/'backup'; mods=game/'ShooterGame'/'Content'/'Mods'/'42'
            (mods).mkdir(); (mods/'example.uasset').write_bytes(b'other-mod'); (mods/'keep.mod').write_bytes(b'mod-meta')
            result=self.run_cli('install','--game',root/'missing','--overlay',overlay,'--id','42','--backup',backup,ok=False)
            self.assertIn('Bad game path',result.stderr); self.assertFalse(backup.exists())
            self.assertEqual((mods/'example.uasset').read_bytes(),b'other-mod')
            result=self.run_cli('install','--game',game,'--overlay',overlay,'--id','42','--backup',backup,ok=False)
            self.assertIn('unknown installed version',result.stderr)
            self.assertFalse(backup.exists()); self.assertEqual((mods/'example.uasset').read_bytes(),b'other-mod')
            self.assertEqual((mods/'keep.mod').read_bytes(),b'mod-meta')
            (mods/'example.uasset').unlink(); (mods/'example.uasset').symlink_to(root/'outside.txt')
            (root/'outside.txt').write_bytes(b'outside')
            result=self.run_cli('install','--game',game,'--overlay',overlay,'--id','42','--backup',backup,ok=False)
            self.assertIn('escapes',result.stderr); self.assertFalse(backup.exists())
            self.assertEqual((root/'outside.txt').read_bytes(),b'outside')
            manifest=json.loads((overlay/'manifest.json').read_text(encoding='utf-8'))
            manifest['files'][0]['path']='../example.uasset'
            (overlay/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            self.run_cli('install','--game',game,'--overlay',overlay,'--id','42','--backup',backup,ok=False)
            self.assertFalse(backup.exists())
    def test_install_rolls_back_a_partial_copy(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); game=make_game(root/'ARK')
            overlay=make_overlay(root/'overlay',[('example.uasset',b'original',b'patched'),('second.uasset',b'old',b'new')])
            mods=game/'ShooterGame'/'Content'/'Mods'/'42'; mods.mkdir()
            (mods/'example.uasset').write_bytes(b'original'); (mods/'second.uasset').write_bytes(b'old')
            (mods/'keep.mod').write_bytes(b'mod-meta')
            backup=root/'backup'; real=ase_localize.write_bytes; state={'tripped':False}
            def fail_second(path,data):
                if Path(path).name=='second.uasset' and 'Mods' in Path(path).parts and not state['tripped']:
                    state['tripped']=True; raise OSError('disk full')
                return real(path,data)
            with unittest.mock.patch.object(ase_localize,'write_bytes',fail_second):
                with self.assertRaises(ValueError) as caught:
                    ase_localize.install_overlay(argparse.Namespace(game=str(game),overlay=str(overlay),id='42',backup=str(backup)))
            self.assertIn('game files restored',str(caught.exception))
            self.assertFalse(backup.exists())
            self.assertEqual((mods/'example.uasset').read_bytes(),b'original')
            self.assertEqual((mods/'second.uasset').read_bytes(),b'old')
            self.assertEqual((mods/'keep.mod').read_bytes(),b'mod-meta')
    def test_install_copies_only_after_preflight(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); game=make_game(root/'runneradmin'/'ARK')
            overlay=make_overlay(root/'overlay',[('example.uasset',b'original',b'patched')])
            mods=game/'ShooterGame'/'Content'/'Mods'/'42'
            (mods).mkdir(); (mods/'example.uasset').write_bytes(b'original'); (mods/'keep.mod').write_bytes(b'mod-meta')
            (mods/'other.uasset').write_bytes(b'leave-me')
            backup=root/'backup'
            result=self.run_cli('install','--game',str(game).replace('/','\\'),'--overlay',root/'overlay','--id','42','--backup',backup)
            report=json.loads(result.stdout)
            self.assertEqual(report['copied_files'],1); self.assertFalse(report['game_tested'])
            self.assertEqual((mods/'example.uasset').read_bytes(),b'patched')
            self.assertEqual((mods/'keep.mod').read_bytes(),b'mod-meta')
            self.assertEqual((mods/'other.uasset').read_bytes(),b'leave-me')
            self.assertFalse((mods/'manifest.json').exists())
            self.assertEqual((backup/'example.uasset').read_bytes(),b'original')
            saved=json.loads((backup/'backup_manifest.json').read_text(encoding='utf-8'))
            self.assertFalse(saved['game_tested']); self.assertIn('Not an in-game test',saved['note'])
            self.run_cli('install','--game',game,'--overlay',overlay,'--id','42','--backup',root/'backup-again')
            self.assertEqual((mods/'example.uasset').read_bytes(),b'patched')
            fresh=make_overlay(root/'fresh',[('nested/example.uasset',b'original',b'patched')])
            self.run_cli('install','--game',game,'--overlay',fresh,'--id','7','--backup',root/'backup-new')
            created=game/'ShooterGame'/'Content'/'Mods'/'7'/'nested'/'example.uasset'
            self.assertEqual(created.read_bytes(),b'patched')
            created_manifest=json.loads((root/'backup-new'/'backup_manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(created_manifest['files'][0]['action'],'created')
            self.assertFalse((root/'backup-new'/'nested'/'example.uasset').exists())

class ReexportPreflightTests(unittest.TestCase):
    def test_python_exporter_uses_interpreter_and_resolved_path(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); game=make_game(root/'runneradmin'/'ARK')
            tool=root/'runneradmin'/'export_tool'
            tool.write_text("#!/usr/bin/env python3\nimport pathlib,sys\n"
                            "target=pathlib.Path(sys.argv[2])\n"
                            "pathlib.Path(str(target)+'.txt').write_text('k=patched\\n',encoding='utf-8')\n",
                            encoding='utf-8')
            tool.chmod(0o644)
            resolved,argv=ase_localize.tool_command(root/'RUNNER~1'/'export_tool')
            self.assertEqual(argv[0],sys.executable)
            self.assertTrue(ase_localize.same_path(resolved,tool))
            self.assertTrue(ase_localize.same_path(argv[1],root/'RUNNER~1'/'export_tool'))
            exe=root/'UE4localizationsTool.exe'; exe.write_bytes(b'MZ-stand-in')
            _exe,exe_argv=ase_localize.tool_command(exe)
            self.assertEqual(exe_argv,[str(_exe)])
            overlay=make_overlay(root/'overlay',[('example.uasset',b'original',b'patched')])
            manifest=json.loads((overlay/'manifest.json').read_text(encoding='utf-8'))
            manifest['files'][0]['edits']=[{'translation':'patched','key':'Name','export_index':0}]
            (overlay/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            import tool_reexport
            work=root/'work'; stdout=io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code=tool_reexport.main(['--tool',str(root/'RUNNER~1'/'export_tool'),'--overlay',str(overlay),
                                         '--work',str(work),'--game',str(root/'RUNNER~1'/'ARK')])
            self.assertEqual(code,0,stdout.getvalue())
            report=json.loads((work/'reexport_report.json').read_text(encoding='utf-8'))
            self.assertEqual(report['matched_fields'],1); self.assertFalse(report['game_tested'])
            self.assertEqual(report['failures'],[]); self.assertEqual(report['missing'],[])
            self.assertEqual((game/'Tools'/'LocalizationManager'/'LocalizationManager.exe').read_bytes(),b'MZ-localization-manager')
            blocked=game/'ShooterGame'/'Content'/'reexport-work'; stderr=io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code=tool_reexport.main(['--tool',str(tool),'--overlay',str(overlay),'--work',str(blocked),
                                         '--game',str(game)])
            self.assertEqual(code,1); self.assertIn('outside the game tree',stderr.getvalue()); self.assertFalse(blocked.exists())
    def test_reexport_stops_before_a_partial_work_directory(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); overlay=make_overlay(root/'overlay',[('example.uasset',b'original',b'patched'),
                                                               ('second.uasset',b'old',b'new')])
            tool=root/'export_tool.py'
            tool.write_text('#!/usr/bin/env python3\n',encoding='utf-8')
            import tool_reexport
            (overlay/'second.uasset').unlink(); (overlay/'second.uasset').mkdir()
            work=root/'work'; stderr=io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code=tool_reexport.main(['--tool',str(tool),'--overlay',str(overlay),'--work',str(work)])
            self.assertEqual(code,1); self.assertIn('Unreadable file',stderr.getvalue()); self.assertFalse(work.exists())
            (overlay/'second.uasset').rmdir(); (overlay/'second.uasset').write_bytes(b'changed')
            stderr=io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code=tool_reexport.main(['--tool',str(tool),'--overlay',str(overlay),'--work',str(work),'--game',str(root/'missing-game')])
            self.assertEqual(code,1); self.assertIn('Bad game path',stderr.getvalue()); self.assertFalse(work.exists())
            (overlay/'second.uasset').write_bytes(b'new')
            real=ase_localize.write_bytes
            def fail_second(path,data):
                if Path(path).name=='second.uasset': raise OSError('disk full')
                return real(path,data)
            with unittest.mock.patch.object(tool_reexport,'write_bytes',fail_second):
                stderr=io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    code=tool_reexport.main(['--tool',str(tool),'--overlay',str(overlay),'--work',str(work)])
            self.assertEqual(code,1); self.assertIn('disk full',stderr.getvalue()); self.assertFalse(work.exists())

if __name__=='__main__': unittest.main()
