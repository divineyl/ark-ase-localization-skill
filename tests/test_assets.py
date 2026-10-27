from pathlib import Path
import json,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills'/'ark-ase-localization'/'scripts'))
from fixtures import asset,compressed
from ase_assets import Package,patch,validate_json_change,unpack_bytes

class AssetTests(unittest.TestCase):
    def rows(self,data): return Package(data).records()[0]
    def test_profiles_and_nested_buff(self):
        for ver in (402,404):
            data=asset(ver); p=Package(data)
            row=next(r for r in self.rows(data) if r['key']=='ModifierName')
            after,edits=patch(data,[{**row,'translation':'寒冷光环'}])
            self.assertNotEqual(after,data)
            self.assertEqual(len(edits),1)
            self.assertEqual(Package(after).names,p.names)
            self.assertIn('寒冷光环',[r['source'] for r in self.rows(after)])
            inverse=[{**e,'source':e['translation'],'translation':e['source']} for e in edits]
            self.assertTrue(patch(after,inverse)[0]==data)
    def test_scoped_reverse_when_translations_collide(self):
        data=asset(404)
        plan=[{**r,'translation':'标签：'} for r in self.rows(data) if r['source'] in {'Label:','LABEL:'}]
        after,edits=patch(data,plan)
        self.assertEqual(len(edits),2)
        inverse=[{**e,'source':e['translation'],'translation':e['source']} for e in edits]
        self.assertTrue(patch(after,inverse)[0]==data)
    def test_ftext_identity_and_enum_array(self):
        data=asset(404); original=Package(data)
        plan=[{**r,'translation':'信息'} for r in self.rows(data) if r['source']=='Info']
        after,edits=patch(data,plan)
        self.assertEqual(len(edits),1)
        self.assertIn('信息',[r['source'] for r in self.rows(after)])
        self.assertEqual(Package(after).names,original.names)
        self.assertEqual([(r.get('namespace'),r.get('text_key')) for r in self.rows(data)],
                         [(r.get('namespace'),r.get('text_key')) for r in self.rows(after)])
    def test_internal_tags_rejected(self):
        data=asset()
        row=next(r for r in self.rows(data) if r['key']=='DinoNameTag')
        with self.assertRaises(ValueError): patch(data,[{**row,'translation':'内部名'}])
    def test_unknown_version_and_truncation_rejected(self):
        for data in [asset()[:100],asset()[:-4],asset()[:12]+b'\0\0\0\0'+asset()[16:]]:
            with self.assertRaises(ValueError): Package(data)
    def test_missing_or_wrong_source_rejected(self):
        data=asset(); row=next(r for r in self.rows(data) if r['key']=='ModifierName')
        with self.assertRaises(ValueError): patch(data,[{**row,'source':'wrong','translation':'中文'}])
    def test_empty_is_byte_identical(self): self.assertEqual(patch(asset(),[])[0],asset())
    def test_json_bindings_cannot_change(self):
        old={'NLLabel':'Spawn','BindValue':'Health','EventUID':'SpawnEvent','Min':0}
        validate_json_change('Nucleus_StaticUIConfig',json.dumps(old),json.dumps({**old,'NLLabel':'生成'}))
        for key,value in [('BindValue','生命'),('EventUID','生成'),('Min',10)]:
            with self.assertRaises(ValueError):
                validate_json_change('Nucleus_StaticUIConfig',json.dumps(old),json.dumps({**old,key:value}))
    def test_localization_preserves_en_and_keys(self):
        old={'LStrings':[{'Key':'_YES_','EN':'Yes'}]}
        new={'LStrings':[{'Key':'_YES_','EN':'Yes','ZH':'是'}]}
        validate_json_change('MOD_LocalizationString',json.dumps(old),json.dumps(new))
        new['LStrings'][0]['Key']='是'
        with self.assertRaises(ValueError): validate_json_change('MOD_LocalizationString',json.dumps(old),json.dumps(new))
    def test_placeholders_are_checked_per_language_not_whole_json(self):
        old={'LStrings':[{'Key':'_COUNT_','EN':'Loaded __0__ items.'}]}
        new={'LStrings':[{'Key':'_COUNT_','EN':'Loaded __0__ items.','ZH':'已加载 __0__ 个物品。'}]}
        validate_json_change('MOD_LocalizationString',json.dumps(old),json.dumps(new))
        new['LStrings'][0]['ZH']='已加载 __1__ 个物品。'
        with self.assertRaises(ValueError): validate_json_change('MOD_LocalizationString',json.dumps(old),json.dumps(new))
    def test_unpack_checks_chunks(self):
        data=asset(); self.assertEqual(unpack_bytes(compressed(data)),data)
        for bad in [compressed(data)[:-1],b'bad-header',b'\0'*32]:
            with self.assertRaises(ValueError): unpack_bytes(bad)

if __name__=='__main__': unittest.main()
