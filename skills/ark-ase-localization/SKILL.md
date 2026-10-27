---
name: ark-ase-localization
description: "Use when localizing ARK Survival Evolved (ASE) Steam Workshop mods, auditing untranslated Buff/HUD/widget text, or building verified Chinese localization overlays for legacy cooked .uasset files. Not for ARK Survival Ascended (ASA), general Unreal projects, or gameplay changes."
license: MIT
---

# 方舟 ASE 模组汉化

把用户提供的 ASE 模组制作成可核查、可回滚的汉化覆盖补丁。输入可以是工坊 ID、已安装模组目录、工坊 `.z` 缓存或已有汉化包；输出包括译文清单、源件哈希、验证结果和覆盖包。

## 操作流程

1. **确认文件**：按用户提供的 ID 查 Steam 库下的 `Mods` 和 `workshop/content/346110`。只有缓存时使用 `WindowsNoEditor` 副本解压；Mods 中没有目录不等于没下载。缺文件时先查可用目录，再问缺失路径。见 [文件发现与完整流程](references/workflow.md)。
2. **识别格式**：先读头和表结构。附带脚本仅支持实测的 `402/7`、`404/10` 两种布局；版本号相同也不能跳过结构检查。未知格式和 external bulk 保留原件并报告，不修改头来绕过拒绝。见 [资源布局](references/ase-format.md)。
3. **提取与审稿**：区分显示字段、内部标识符和运行时内容。读不到 Buff 时检查 `BuffDescription`；UI 检查 FText、FText 数组和 JSON。保留原始命名空间、键、事件、绑定、权限和类路径。见 [UI 与 JSON](references/ui-and-json.md)。
4. **翻译与写回**：按文件哈希及 `export_index + property_path + text_index` 定位；不要只凭原文或译文字典替换。按用户要求决定双语名称，紧凑按钮优先短中文。保留数值、占位符、富文本标签。具体模组术语不能当成跨模组通用规则。
5. **验证后交付**：重新解析、定点读回、按位置反向还原且逐字节一致，核对未修改导出块及名称表，再用独立工具只读重导出。明确哪些检查未完成。分别统计资源文件、修改字段、JSON 内文字和唯一译文；文件通过不等于游戏 UI 全部通过。见 [验证与发布](references/validation-and-release.md)。

## 脚本入口

Python 3.10+，仅标准库。从本 Skill 目录执行；原件与输出目录分开，所有输出拒绝覆盖现有路径：

```bash
python scripts/ase_localize.py discover --id 2566418613 --library "/path/to/SteamLibrary"
python scripts/ase_localize.py unpack --input "/path/to/WindowsNoEditor" --output "./work/original"
python scripts/ase_localize.py extract --input "./work/original" --output "./work/plan.json"
```

在提取记录中，仅为确定要翻译的项增加 `translation`。保持 `source_sha256`、定位字段及 `source` 不变；内部字段即使被提取，也不是翻译目标。复核 JSON 结构后：

```bash
python scripts/ase_localize.py patch --input "./work/original" --plan "./work/plan.json" --output "./work/overlay"
python scripts/ase_localize.py verify --source "./work/original" --overlay "./work/overlay"
python scripts/ase_localize.py package --source "./work/original" --overlay "./work/overlay" --id 2566418613 --output "./work/patch.zip"
```

附带脚本不会安装、订阅模组、改 `.mod` 或启动游戏。制作补丁不自动意味着安装或对外发布授权；按当前用户请求交付。允许安装时先退出游戏和服务器、校验现装版本、备份并准备恢复，禁止直接覆盖未知版本。

## 容易误判的边界

- `DinoNameTag`、对象名、NameMap、函数名、资源路径属于内部标识；扫描器显示英文不构成修改它们的理由。
- 第三方工具 M2 在本流程中用于工作副本的**只读导出**；没有独立验证的 M2 全量导入不应直接用于烹饪资源。
- 新增 Nucleus `ZH` 词条时保留 `EN` 和 `Key`；已有用户语言或自定义译文可能覆盖默认值。不要删除存档来强行切语言。
- 中英文都显示 `_KEY_` 时，核对查表链和游戏本地化资源是否意外翻译了内部字段名；参见 [UI 与 JSON](references/ui-and-json.md) 中的实际案例。不能把个案假设当作通用原因。
- 附带写入器不支持 Kismet 改写、任意 Struct/Array/Map、复杂 FText 历史、纹理文字、ASA、Linux 资源跨平台套用。遇到这些情况报告剩余项，改走已验证的专用工具或 DevKit 路线。
- 参考 [两个实测案例](references/case-studies.md) 学习适用范围；案例数字和术语不是新模组的预期结果。
