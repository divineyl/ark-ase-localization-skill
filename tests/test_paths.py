"""Path normalization. Samples are synthetic directories, not game files."""
import os,sys,tempfile,unittest
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

if __name__=='__main__': unittest.main()
