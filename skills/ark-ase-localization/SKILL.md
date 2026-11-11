---
name: ark-ase-localization
description: "Use when localizing ARK: Survival Evolved (ASE) Steam Workshop mods into Chinese (汉化), auditing untranslated Buff, HUD, widget, or JSON UI text, unpacking WindowsNoEditor .uasset.z caches, or building a verified reversible overlay for cooked .uasset files in the observed 402/7 and 404/10 layouts. Use for 方舟进化, a workshop mod ID, localization overlay, and display-text review. Out of scope: ARK: Survival Ascended (ASA), general Unreal projects, gameplay or Kismet bytecode edits, texture text, and installing the patch into a live game."
license: MIT
---

# 方舟 ASE 模组汉化

把用户提供的 ASE 模组制作成可核查、可回滚的汉化覆盖补丁。输入可以是工坊 ID、已安装模组目录、工坊 `.z` 缓存或已有汉化包。输出包括译文清单、源件哈希、未覆盖项、验证结果和覆盖包。

译文由审稿后写入 `plan.json` 的 `translation` 产生。脚本不自动把英语翻成中文，也不安装、订阅或启动游戏。

## 先定范围

- 确认是 ASE 的 Windows 烹饪资源。ASA、`LinuxNoEditor`、通用 UE 工程和玩法修改都停下来说明范围。
- 原件目录只读。`work/original`、`work/plan.json`、`work/overlay`、`work/patch.zip` 都用新路径，放在原件外面。
- 只给 `display_candidate` 为 true、并且审过的记录追加 `translation`。`DinoNameTag`、对象名、NameMap、函数名和资源路径保持原样。
- 保留 `source_sha256`、`path`、`export_index`、`property_path`、`text_index`、`key`、`kind`、`source`、`namespace` 和 `text_key`。
- 用户明确要求新配置默认中文时，才把顶层 `allow_language_default` 设为 `true`。这只影响 `MOD_ClientSettings` 的 `EN`/`ZH` 切换。
- 用户没有提供 UE4LocalizationsTool 时，独立导出记为 `not_run`。不下载工具，也不把缺检写成通过。

按任务打开一页参考，不必一次读完：

- 找文件、解压、填计划、命令被拒绝：[workflow.md](references/workflow.md)
- 包被拒绝或要核对偏移：[ase-format.md](references/ase-format.md)
- Buff、FText、JSON 叶子：[ui-and-json.md](references/ui-and-json.md)
- 统计口径、压缩包和安装条件：[validation-and-release.md](references/validation-and-release.md)
- 案例里的数字和术语只属于那一个模组：[case-studies.md](references/case-studies.md)

## 用户说法对应的第一步

| 用户给出的材料 | 第一步 |
| --- | --- |
| 工坊 ID，可能在某个 Steam 库 | `discover`。退出码 0 且 `candidates` 为空时，展示 `searched_libraries` 并询问路径 |
| `WindowsNoEditor` 缓存，或含 `.z` 的目录 | `unpack` 到新的 `work/original` |
| 已经解压的 `.uasset` 目录 | 先复制成快照，再 `extract` |
| 要求先看有哪些文字 | 只交付计划、计数和未覆盖项，停在写回之前 |
| 游戏里仍有英文或 `_KEY_` | 先比对用户实际启动目录里的文件哈希，再查未覆盖项和 [查表案例](references/ui-and-json.md) |
| 要求安装进游戏 | 先完成离线验证。安装步骤只在用户明确要求后、按发布说明手工进行；附带命令不写入游戏目录 |

## 操作流程

1. **确认文件**。按 ID 查找 `Mods/<ID>` 和 `workshop/content/346110/<ID>/WindowsNoEditor`。Mods 里没有目录，只说明安装副本不在该路径。非 Windows 必须带 `--library`。详见 [文件发现](references/workflow.md)。
2. **解压并识别格式**。附带脚本只接受实测的 `402/7` 和 `404/10`，版本号相同也要过结构检查。未知格式、external bulk 和 `.umap` 保留原件并写入未覆盖列表。见 [资源布局](references/ase-format.md)。
3. **提取与审稿**。区分显示字段、内部标识和运行时内容。读不到 Buff 时检查 `BuffDescription`；UI 检查 FText、FText 数组和 JSON。白名单和 `opaque` 的含义见 [可写字段](references/workflow.md#可写字段)。
4. **写回**。定位使用文件哈希加上 `export_index + property_path + text_index`。同一中文可以对应多条原文，不能靠译文字典回滚。用户给出的术语优先。未要求双语时，按钮和短标签用简体中文；用户要求名称双语时写成 `中文 (English)`。保留数值、`__数字__`、换行和富文本标签。空说明保持空白，不为专有生物名套用其他模组的译名。
5. **验证后交付**。`patch` 已包含重新解析、定点读回和逐字节反向还原。再用 `verify`。只有用户提供了工具才运行 `tool_reexport.py`，然后把报告传给 `package`。分别报告资源文件、修改字段、JSON 内文字和唯一译文；文件通过不等于游戏 UI 全部通过。见 [验证与发布](references/validation-and-release.md)。

标准错误以 `ERROR:` 开头且退出码为 1 时，停止写回并向用户引用该句。不要改版本号、跳过哈希或放宽 JSON 检查后再试。对应处理见 [命令拒绝时](references/workflow.md#命令拒绝时)。

## 脚本入口

Python 3.10+，仅标准库。在本 Skill 目录执行；系统里的命令名是 `python3` 时，替换下面的 `python`。

```bash
python scripts/ase_localize.py discover --id 2566418613 --library "/path/to/SteamLibrary"
python scripts/ase_localize.py unpack --input "/path/to/WindowsNoEditor" --output "./work/original"
python scripts/ase_localize.py extract --input "./work/original" --output "./work/plan.json"
python scripts/ase_localize.py patch --input "./work/original" --plan "./work/plan.json" --output "./work/overlay"
python scripts/ase_localize.py verify --source "./work/original" --overlay "./work/overlay"
python scripts/ase_localize.py package --source "./work/original" --overlay "./work/overlay" --id 2566418613 --output "./work/patch.zip"
```

用户提供了工具时才追加：

```bash
python scripts/tool_reexport.py --tool "/path/to/UE4localizationsTool.exe" --overlay "./work/overlay" --work "./work/tool-check"
python scripts/ase_localize.py package --source "./work/original" --overlay "./work/overlay" --id 2566418613 --output "./work/patch.zip" --reexport-report "./work/tool-check/reexport_report.json"
```

允许安装时先退出游戏和服务器、校验现装版本、备份并准备恢复。禁止直接覆盖未知版本。制作补丁不自动获得对外发布授权。

## 容易误判的边界

- 第三方工具的 M2 模式在本流程中只用于工作副本的只读导出。没有独立验证的 M2 全量导入不用于烹饪资源。
- 新增 Nucleus `ZH` 时保留 `EN` 和 `Key`。写入器保持原有语言项数量。已有用户语言或自定义译文可能覆盖默认值。
- 中英文都显示 `_KEY_` 时，先核对实际加载的文件哈希，再核对查表链。个案不能当成所有模组的原因，见 [UI 与 JSON](references/ui-and-json.md)。
- 附带写入器不支持 Kismet 改写、任意 Struct/Array/Map、复杂 FText 历史、纹理文字、ASA，以及把 Linux 资源套到 Windows。遇到这些情况报告路径、类型和原因。
- [两个实测案例](references/case-studies.md) 用来学习适用范围。案例中的文件数、术语和字节码修复不是新模组的预期结果，也不是本脚本的功能。
