from pathlib import Path
import json,struct,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills'/'ark-ase-localization'/'scripts'))
from fixtures import asset,compressed
from ase_assets import Package,patch,validate_json_change,unpack_bytes
from ase_localize import text_pairs

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
        for key,value in [('BindValue','生命'),('BindText','生成'),('EventUID','生成'),('Permission','生成'),('Min',10)]:
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
        sentinel=bytearray(compressed(data,131072)); struct.pack_into('<q',sentinel,8,-1641380927)
        self.assertEqual(unpack_bytes(bytes(sentinel)),data)
    def test_enum_terminator_and_bulk_are_not_text(self):
        rows=self.rows(asset())
        self.assertFalse(next(r for r in rows if r['source']=='MAX')['display_candidate'])
        self.assertTrue(next(r for r in rows if r['source']=='Info')['display_candidate'])
        raw=bytearray(asset()); struct.pack_into('<q',raw,147,1)
        with self.assertRaises(ValueError): Package(bytes(raw))
    def test_ftext_keys_and_unknown_history(self):
        data=asset(texts=[('TooltipText','Tip'),('ButtonText','Press'),('HintText','Type here',1)])
        rows,opaque=Package(data).records()
        tip=next(r for r in rows if r['key']=='TooltipText')
        button=next(r for r in rows if r['key']=='ButtonText')
        self.assertTrue(tip['display_candidate']); self.assertFalse(button['display_candidate'])
        self.assertFalse(any(r['key']=='HintText' for r in rows))
        self.assertTrue(any(item.get('key')=='HintText' for item in opaque))
        after,edits=patch(data,[{**tip,'translation':'提示'}])
        self.assertEqual([r['source'] for r in self.rows(after) if r['key']=='TooltipText'],['提示'])
        self.assertEqual(patch(after,[{**e,'source':e['translation'],'translation':e['source']} for e in edits])[0],data)
        with self.assertRaises(ValueError): patch(data,[{**button,'translation':'按下'}])
    def test_placeholders_tokens_and_paths_round_trip(self):
        data=asset(strings=[('HUDMessage','Loaded __0__ items.')])
        row=next(r for r in self.rows(data) if r['key']=='HUDMessage')
        after,edits=patch(data,[{**row,'translation':'已加载 __0__ 个物品。'}])
        self.assertEqual(patch(after,[{**e,'source':e['translation'],'translation':e['source']} for e in edits])[0],data)
        with self.assertRaises(ValueError): patch(data,[{**row,'translation':'已加载 __1__ 个物品。'}])
        for source in ('_YES_','_YES','$$Ark-Nucleus$:$OK_BTN','/Game/Example','/Ark-Nucleus/Example'):
            token=asset(strings=[('HUDMessage',source)])
            item=next(r for r in self.rows(token) if r['key']=='HUDMessage')
            with self.assertRaises(ValueError): patch(token,[{**item,'translation':'译文'}])
        prose=asset(strings=[('HUDMessage','YES_')])
        item=next(r for r in self.rows(prose) if r['key']=='HUDMessage')
        patched,edits=patch(prose,[{**item,'translation':'是'}])
        self.assertEqual(patch(patched,[{**e,'source':e['translation'],'translation':e['source']} for e in edits])[0],prose)
    def test_json_tokens_names_and_official_ui_fields(self):
        token={'Label':'$$Ark-Nucleus$:$OK_BTN','EventUID':'Stay','Permission':'Nucleus_Example'}
        with self.assertRaises(ValueError):
            validate_json_change('N_BaseWidget_StaticUIConfig',json.dumps(token),json.dumps({**token,'Label':'确定'}))
        prose={'Label':'OK','Title':'Spawn __0__','Note':'Hint','Placeholder':'Name','EventUID':'Stay','Permission':'Nucleus_Example'}
        translated={**prose,'Label':'确定','Title':'生成 __0__','Note':'提示','Placeholder':'名称'}
        validate_json_change('N_BaseWidget_StaticUIConfig',json.dumps(prose),json.dumps(translated))
        with self.assertRaises(ValueError):
            validate_json_change('N_BaseWidget_StaticUIConfig',json.dumps(prose),json.dumps({**prose,'Permission':'生成'}))
        with self.assertRaises(ValueError):
            validate_json_change('N_BaseWidget_StaticUIConfig',json.dumps(prose),json.dumps({**prose,'Title':'生成 __1__'}))
        named={'Name':'$$Ark-Nucleus$:$STATE_PASSIVE','EnumID':1}
        with self.assertRaises(ValueError):
            validate_json_change('TestUIConfig',json.dumps(named),json.dumps({**named,'Name':'被动'}))
        visible={'Name':'Passive','EnumID':1}
        validate_json_change('TestUIConfig',json.dumps(visible),json.dumps({**visible,'Name':'被动'}))
        with self.assertRaises(ValueError):
            validate_json_change('TestUIConfig',json.dumps({'Name':'Passive'}),json.dumps({'Name':'被动'}))
        data=asset(404,strings=[('N_BaseWidget_StaticUIConfig',json.dumps(prose))])
        row=next(r for r in self.rows(data) if r['key']=='N_BaseWidget_StaticUIConfig')
        after,edits=patch(data,[{**row,'translation':json.dumps(translated,ensure_ascii=False)}])
        self.assertEqual(patch(after,[{**e,'source':e['translation'],'translation':e['source']} for e in edits])[0],data)
        self.assertEqual(len(list(text_pairs(edits[0]))),4)
    def test_language_table_and_display_names(self):
        old={'SERVER':{'HOME':{'en':'Home','de':'Zuhause','zh-TW':'首頁'}}}
        new={'SERVER':{'HOME':{'en':'Home','de':'Zuhause','zh-TW':'首頁','zh':'首页'}}}
        validate_json_change('Nucleus_ServerLocalization_Default',json.dumps(old),json.dumps(new,ensure_ascii=False))
        for bad in (
            {'SERVER':{'HOME':{'en':'House','de':'Zuhause','zh-TW':'首頁','zh':'首页'}}},
            {'SERVER':{'HOME':{'en':'Home','de':'家','zh-TW':'首頁'}}},
            {'SERVER':{'HOME':{'en':'Home','de':'Zuhause','zh-TW':'家'}}},
            {'SERVER':{'HOME':{'en':'Home','de':'Zuhause','zh-TW':'首頁'},'EXTRA':{'en':'Extra'}}},
        ):
            with self.assertRaises(ValueError):
                validate_json_change('Nucleus_ServerLocalization_Default',json.dumps(old),json.dumps(bad,ensure_ascii=False))
        counted={'YES':{'en':'Loaded __0__ items.'}}
        done={'YES':{'en':'Loaded __0__ items.','zh':'已加载 __0__ 个物品。'}}
        validate_json_change('MyMod_LocalizationStrings',json.dumps(counted),json.dumps(done,ensure_ascii=False))
        done['YES']['zh']='已加载 __1__ 个物品。'
        with self.assertRaises(ValueError):
            validate_json_change('MyMod_LocalizationStrings',json.dumps(counted),json.dumps(done,ensure_ascii=False))
        data=asset(404,strings=[('Nucleus_ServerLocalization_Default',json.dumps(old))])
        row=next(r for r in self.rows(data) if r['key']=='Nucleus_ServerLocalization_Default')
        after,edits=patch(data,[{**row,'translation':json.dumps(new,ensure_ascii=False)}])
        self.assertEqual(list(text_pairs(edits[0])),[('Home','首页')])
        self.assertEqual(patch(after,[{**e,'source':e['translation'],'translation':e['source']} for e in edits])[0],data)
        names={'zh':{'Name':'Chinese - Simplified','NativeName':'中文'},'en':{'Name':'English','NativeName':'English'},'zh-TW':{'Name':'Chinese - Traditional','NativeName':'中文'}}
        renamed=json.loads(json.dumps(names)); renamed['zh']['Name']='简体中文'
        for key in ('Languages','N_EditLangDrop_SupportedLanguages'):
            validate_json_change(key,json.dumps(names),json.dumps(renamed,ensure_ascii=False))
        renamed['en']['Name']='英文'
        with self.assertRaises(ValueError):
            validate_json_change('N_EditLangDrop_SupportedLanguages',json.dumps(names),json.dumps(renamed,ensure_ascii=False))
        upper={'ZH':{'Name':'Chinese','NativeName':'Chinese'}}
        changed={'ZH':{'Name':'简体中文','NativeName':'中文'}}
        validate_json_change('Languages',json.dumps(upper),json.dumps(changed,ensure_ascii=False))
    def test_language_default_requires_flag_and_map_properties_stay_closed(self):
        old={'CoreClientSettings':{'Language':'EN','Volume':1}}
        changed={'CoreClientSettings':{'Language':'ZH','Volume':1}}
        with self.assertRaises(ValueError):
            validate_json_change('MOD_ClientSettings',json.dumps(old),json.dumps(changed))
        validate_json_change('MOD_ClientSettings',json.dumps(old),json.dumps(changed),allow_language_default=True)
        with self.assertRaises(ValueError):
            validate_json_change('MOD_ClientSettings',json.dumps(old),json.dumps({'CoreClientSettings':{'Language':'ZH','Volume':2}}),allow_language_default=True)
        data=asset(strings=[('MOD_ClientSettings',json.dumps(old))])
        row=next(r for r in self.rows(data) if r['key']=='MOD_ClientSettings')
        after,edits=patch(data,[{**row,'translation':json.dumps(changed)}],allow_language_default=True)
        self.assertEqual(patch(after,[{**e,'source':e['translation'],'translation':e['source']} for e in edits],allow_language_default=True)[0],data)
        self.assertEqual(list(text_pairs(edits[0])),[])
        locked=asset(strings=[('MyMod_LocStrings','{"GENERAL":"{}"}')])
        item=next(r for r in self.rows(locked) if r['key']=='MyMod_LocStrings')
        self.assertFalse(item['display_candidate'])
        with self.assertRaises(ValueError): patch(locked,[{**item,'translation':'{"GENERAL":"{}"}'}])
        plain=next(r for r in self.rows(asset()) if r['key']=='ModifierName')
        with self.assertRaises(ValueError): patch(asset(),[{**plain,'translation':'寒\0冷'}])
        with self.assertRaises(ValueError): patch(asset(),[{**plain,'translation':'甲'},{**plain,'translation':'乙'}])

if __name__=='__main__': unittest.main()
