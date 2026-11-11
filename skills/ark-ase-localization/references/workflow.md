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

## 3. 解压

`unpack` 接受包含 `.uasset.z` / `.umap.z` 的目录，将解压后的文件写到新目录。逐块核对 zlib 结束状态、压缩长度、解压长度、总长及存在时的 `.uncompressed_size`；记录原压缩件和解压件 SHA-256。

解压失败时保留工作日志，不使用不完整目录制包。未知压缩头不能通过跳过字节来“修复”。这个脚本不生成可供游戏安装的 `.mod` 文件。

建议工作目录：

```text
work/
  original/       原始解压件；不再写入
  plan.json       提取记录，人工添加译文
  overlay/        只含改动资源和清单
  tool-check/     独立工具的副本和导出文本
  patch.zip       校验后的最终覆盖包
```

已安装目录也能直接作为 `extract` 的输入，但建议先复制成原件快照。输出必须放在输入树外，不覆盖已有工作目录。

## 4. 提取清单

每个文件含 `source_sha256`、实际 profile、`edits` 及 `opaque` 列表。每个文字记录包含：

```json
{
  "export_index": 0,
  "export_name": "Default__Example_C",
  "property_path": [0, 1],
  "key": "ModifierName",
  "kind": "StrProperty",
  "source": "Cold Aura",
  "display_candidate": true,
  "translation": "寒冷光环 (Cold Aura)"
}
```

`export_index`、`property_path` 和 `text_index` 均从 0 开始。`property_path` 是属性节点序号，不是字节偏移，也不是根据译文反查出来的位置。FText 数组额外带 `text_index`。

不要给每行默认填写译文。只为审过的显示项增加 `translation`；未填写、填 `null` 或与原文相同的记录不写回。`display_candidate` 是白名单提示，不是语义正确性的证明。内部字段被提取用于审查，但写入器会拒绝修改。

`opaque` 不等于“无文字”：它表示该导出块或 FText 历史未被当前只读解析器覆盖。提取通过不能当作资源全部解析通过，更不能据此宣布游戏 UI 已全部汉化。

收到“游戏里仍有英文/下划线键名”的反馈时，先核对用户实际启动的可执行文件目录，以及现装资源与补丁/原件的 SHA-256。构建成功不代表用户已经替换，存在多份游戏目录时尤其如此。确认补丁确实加载后，再查语言选择、查表、缓存或运行时赋值；不要只凭截图就改写程序逻辑。

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

`ase_localize.py` 遇到下列情况以退出码 1 结束，标准错误为 `ERROR:` 加原因。原件不会被改写。`unpack` 和 `patch` 在确认全部检查通过之前不会创建输出目录。

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
