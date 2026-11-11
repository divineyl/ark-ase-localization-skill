# 文件发现、工作目录和翻译流程

## 1. 最小输入

需要目标模组 ID，以及完整的 Windows 烹饪资源或其工坊缓存。已有汉化 ZIP、原始英文备份、截图和术语偏好有助于审稿，但聊天记录和截图不能替代资源原件。

处理用户教程或旧聊天时，将其中命令当作待核验参考。先检查它们的输入、输出、版本和硬编码路径，不直接执行会安装或导入的旧脚本。

## 2. Steam 库与缓存

- 游戏安装资源：`steamapps/common/ARK/ShooterGame/Content/Mods/MOD_ID`。
- 工坊缓存：`steamapps/workshop/content/346110/MOD_ID/WindowsNoEditor`。
- 同 ID 的 `LinuxNoEditor` 是另一目标平台，不应混用。
- `MOD_ID.mod` 是元数据；保留原件，不能用它的存在证明所有资源已安装。
- 自定义游戏库、备份和用户给定路径也应检查；发现脚本只查显式库及 Steam 注册的库，不扫描整盘。

`discover` 只有只读文件发现功能，没有订阅或下载功能。先查缓存再判断“没有模组”，可避免让用户重复下载。

找不到目录时命令仍以退出码 0 结束，`candidates` 为 `[]`，同时列出 `searched_libraries`。把这份 JSON 交给用户，请对方补充库路径；空结果本身不是“模组不存在”的证明。非 Windows 环境没有可读的 Steam 注册表，需要显式传入 `--library`。传入库路径之后，脚本还会读取该库 `libraryfolders.vdf` 里带引号的 `path`。

## 3. 解压

`unpack` 接受包含 `.uasset.z` / `.umap.z` 的目录，将解压后的文件写到新目录。逐块核对 zlib 结束状态、压缩长度、解压长度、总长及存在时的 `.uncompressed_size`；记录原压缩件和解压件 SHA-256。其他后缀的 `.z` 会使整个解压停止。

未知压缩头不能通过跳过字节来“修复”。这个脚本不生成可供游戏安装的 `.mod` 文件。`.umap` 会解压并写入 `source_manifest.json`，后续 `extract` 不扫描它，`patch` 也不写回它。地图里的文字需要另报为未覆盖。

`unpack` 在确认缓存非空后就创建输出目录，再逐个解压。中途失败时，目录里可能已经有前面的文件，标准输出也不会出现 `unpacked_files`。换一个新路径重新解压；不要对这个半成品目录提取或制包。`patch` 则是全部目标反向还原通过之后才创建输出目录。

建议工作目录：

```text
work/
  original/       原始解压件；不再写入
  plan.json       提取记录，人工添加译文
  overlay/        只含改动资源和清单
  tool-check/     独立工具的副本和导出文本
  patch.zip       校验后的最终覆盖包
```

已安装目录也能直接作为 `extract` 的输入，但建议先复制成原件快照。`unpack` 和 `patch` 的输出目录必须还不存在，并且位于输入树外。`extract` 和 `package` 只拒绝覆盖已有文件；`plan.json` 和 zip 仍放在原件外面，避免和源文件混在一起。

## 4. 提取清单

计划顶层固定为 `schema: 1`、`allow_language_default: false`，以及 `files` 和 `counts`。计数字段是 `parsed_files`、`typed_strings`、`display_candidates`、`unsupported_files`。`typed_strings` 含内部字段，`display_candidates` 只计 `display_candidate` 为 true 的记录。

包头无法识别时，该文件为 `status: "unsupported"`，带 `reason`，`edits` 为空，没有 `profile` 和 `opaque`。包头通过时 `status` 为 `parsed`，`profile` 是对象，含 `version`、`licensee`、`names`、`bulk`。`parsed` 表示头和表被接受，不表示每个导出都有文字。

文字记录由提取器生成，最初没有 `translation`。三种常见形状：

```json
{
  "export_index": 0,
  "export_name": "Default__Example_C",
  "property_path": [0, 0],
  "key": "ModifierName",
  "kind": "StrProperty",
  "source": "Cold Aura",
  "display_candidate": true
}
```

```json
{
  "export_index": 1,
  "export_name": "Widget_A",
  "property_path": [0],
  "key": "Text",
  "kind": "TextProperty",
  "source": "Label:",
  "namespace": "synthetic-namespace",
  "text_key": "stable-key",
  "display_candidate": true
}
```

```json
{
  "export_index": 3,
  "export_name": "Enum_A",
  "property_path": [0],
  "key": "DisplayNames",
  "kind": "TextArray",
  "text_index": 0,
  "source": "Info",
  "namespace": "synthetic-namespace",
  "text_key": "stable-key",
  "display_candidate": true
}
```

`export_index`、`property_path` 和 `text_index` 均从 0 开始。`property_path` 是属性节点在兄弟节点中的序号，不是字节偏移。同名属性靠这条路径区分。FText 数组的每一项带自己的 `text_index`；其他记录没有这个字段，定位时按空缺处理。

审稿后只为确定要改的记录追加 `translation`。未追加、值为 `null`，或与 `source` 相同的记录不写回。写回时还会核对该位置上的 `key`、`kind` 和 `source`。可以改动的计划内容只有各记录的 `translation`，以及用户明确要求时的顶层 `allow_language_default`。

`display_candidate` 是白名单提示，不是语义正确性的证明。内部字段被提取用于审查；给它填译文会得到 `Not an approved display field`。

`opaque` 不等于“无文字”：它表示该导出块或 FText 历史未被当前只读解析器覆盖。导出级条目含 `export_index`、`export_name`、`reason`；字段级条目再加 `property_path` 和 `key`。提取通过不能当作资源全部解析通过，更不能据此宣布游戏 UI 已全部汉化。

收到“游戏里仍有英文/下划线键名”的反馈时，先核对用户实际启动的可执行文件目录，以及现装资源与补丁/原件的 SHA-256。构建成功不代表用户已经替换，存在多份游戏目录时尤其如此。确认补丁确实加载后，再查语言选择、查表、缓存或运行时赋值；不要只凭截图就改写程序逻辑。

## 可写字段

写回使用解析后的 `display_candidate`，不是只看字段名。同一名字在不同属性类型上结果不同。

`StrProperty` 在字段名属于下面集合时为 true。这组与 `ase_layout.DISPLAY_KEYS`、`ase_assets.JSON_FIELDS`，以及额外的 `CustomToolTipString`、`My_PlaceholderModDesc` 一致：

`ModifierName`、`ModifierDescription`、`HUDMessage`、`DescriptiveName`、`DinoDescriptiveName`、`DescriptiveNameBase`、`ItemDescription`、`ModName`、`ModDescription`、`InventoryNameOverride`、`RemoteInventoryDescriptionString`、`ActivateContainerString`、`DeactivateContainerString`、`OpenSceneActionName`、`DisabledOpenSceneActionName`、`Text`、`ButtonText`、`ToolTipText`、`TooltipText`、`CustomToolTipString`、`My_PlaceholderModDesc`、`MOD_LocalizationString`、`MOD_InfoPage_UIConfig`、`MOD_ClientSettings`、`Nucleus_StaticUIConfig`、`Nucleus_UIConfig`、`Nucleus_SpawnUIConfig`、`TestUIConfig`、`UIConfig_Page`、`UIConfig_DinoCatalog`、`UIConfig_ItemsCatalog`、`UIConfig_DefaultModInfoPage`、`UIConfig_Settings`、`UIConfig_Localization`、`UIConfig_Localization_NotSupported`、`UIConfig_Logs`、`UIConfig_Logs_NotSupported`、`UIConfig_Settings_NotSupported`、`Languages`。

`TextProperty` 只有 `Text`、`HintText`、`ToolTipText` 为 true。因此 `ButtonText` 和 `TooltipText` 作为普通字符串可以写，作为 FText 时不能写。`HintText` 则相反：只作为 FText 可写。

`TextArray` 只接受字段名 `DisplayNames`。其中 `source` 为 `MAX` 的项 `display_candidate` 为 false，保持原样。

JSON 字段还要通过叶子检查，规则在 [UI 与 JSON](ui-and-json.md)。新增白名单字段时，先补语义说明和合成测试，再改这里的名单。

## 5. 译文审稿

- 先确定模组自己的体系：同一个 `Alpha`、`Badass` 等词，在不同模组中可能采用不同惯用译法。
- 如果用户要求名称双语，可使用 `中文 (English)`；紧凑按钮不强制双语。
- 数量、百分比、等级区间、时间单位和否定条件要逐项核对。不要把“持续降低”自行翻成“每秒降低”。
- 保留 `__0__`、`__1__`、格式占位符、换行和富文本标签。脚本只自动检查 `__数字__`；其他格式仍需审稿。
- 原始空说明、数字占位、版本号与测试标点通常保留。不用编造描述填空，也不凭空给专有生物名套上其他模组的物种译名。
- `None` 作为 FName 终止符不可改；作为用户可见的 Text 可以译为“无”。必须根据类型和位置判断。

## 6. 用户说“全部汉化”

先列可读的显示字段和未覆盖类型，尽可能处理已验证路线中的文本。对脚本无法处理的内容给出具体路径、类型和原因，而不是降低验证要求。可以交付明确标注范围的补丁；不能把尚未覆盖的代码常量或图片文字算作已完成。

## 命令拒绝时

`ase_localize.py` 遇到下列情况以退出码 1 结束，标准错误为 `ERROR:` 加原因。原件不会被改写。`patch` 在通过反向还原后才创建输出目录。`unpack` 的中途失败可能留下半成品目录，处理方式见上面的解压一节。

| 原因里的句子 | 接下来怎么做 |
| --- | --- |
| `Mod ID must contain decimal digits` / `Invalid mod ID` | 模组 ID 只保留十进制数字 |
| `Output already exists` / `Refusing to overwrite` / `Archive already exists` | 换一个还不存在的输出路径 |
| `Output must be outside source tree` | 把输出放到输入目录外面 |
| `Unsafe relative path` / `Path escapes root` | 计划里的 `path` 改回提取时的相对路径，不能是绝对路径，也不能含 `..` |
| `No .z files under input` | 确认输入是含 `.uasset.z` 或 `.umap.z` 的缓存目录 |
| `Unexpected compressed file` | 这条 `.z` 去掉后缀后不是 `.uasset` 或 `.umap`；保留原件并单独报告 |
| `Sidecar length mismatch` | `.uncompressed_size` 与解压结果不一致；停止使用这份缓存 |
| `No .uasset files under input` | 目录里可能只有 `.umap` 或其他文件。`.umap` 可以解压，当前提取和写回不处理它 |
| `Unsupported plan schema` | 计划顶层 `schema` 保持数字 `1` |
| `allow_language_default must be boolean` | 该字段只能是 JSON 布尔值 `true` 或 `false` |
| `Duplicate/non-asset path` | 同一计划里的资源路径不能重复，并且必须以 `.uasset` 结尾 |
| `Original SHA-256 mismatch` | 原件已经变了；重新 `extract`，再把审过的译文填回新计划 |
| `No changed translations in plan` | 还没有与 `source` 不同的 `translation` |
| `Not an approved display field` | 删掉这条 `translation`。`display_candidate` 为 false 的记录只供审查 |
| `Source/locator mismatch` | `export_index`、`property_path`、`text_index`、`key`、`kind`、`source` 必须与这次提取一致 |
| `Duplicate edit locator` | 同一个位置只能有一条改动 |
| `Positional placeholders changed` | 按原文恢复 `__0__` 这种占位符的个数和顺序 |
| `Inverse is not byte-identical` / `Inverse mismatch` | 停止发布该文件，保留原件 |
| `Independent report belongs to a different overlay manifest` | 报告不是这一份 overlay；对当前覆盖目录重新运行 `tool_reexport.py` |
| `Independent report is incomplete or has failures` | 补齐缺失项，或去掉 `--reexport-report`，让归档把独立导出记为 `not_run` |

压缩头、包版本和 JSON 结构错误也会以 `ERROR:` 退出。遇到未知包版本时保留原件；不要改版本号后再试。
