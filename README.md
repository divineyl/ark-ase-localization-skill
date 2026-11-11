# Ark ASE Localization Skill · 方舟进化模组汉化技能

将《ARK: Survival Evolved》模组汉化中的可复用经验整理成 Agent Skill，供 Codex 或支持 Agent Skills 的工具使用。既可以让代理按教程工作，也可以直接运行 Python 脚本。

面向 **ASE**，不是 **ASA**。它不是万能反编译器，不生成 DevKit 工程，也不改变模组玩法。

## 包含什么

- 可直接使用的 `SKILL.md`，按需要加载的中文参考教程。
- 工坊缓存发现与解压、类型化文字提取、按位置写回、反向还原、校验和覆盖包生成脚本。
- 两个实测资源布局：402/7 与 404/10；未知结构保留原件并报告。
- Buff 嵌套字段、UMG FText、枚举显示文本和 Nucleus JSON 本地化处理经验。
- 纯合成测试样本、自动测试、独立工具重导出入口和贡献说明。

仓库不包含游戏、模组资产、第三方工具二进制、私人聊天、个人路径或账号凭据。

## 目录与职责

```text
skills/ark-ase-localization/
  SKILL.md                 代理读的操作说明
  agents/openai.yaml       Codex 展示名、短说明和默认提示
  references/              按任务打开的教程
  scripts/ase_layout.py    只读包头、名称表、属性树；显示字段白名单 DISPLAY_KEYS
  scripts/ase_assets.py    文字记录、JSON 校验、按位置写回、.z 解压
  scripts/ase_localize.py  discover / unpack / extract / patch / verify / package
  scripts/tool_reexport.py 可选的外部工具只读导出
tests/                     合成样本。fixtures.py 造包，测试不变量
docs/VALIDATION.md         已发生过的验证记录，不是对未来资源的兼容承诺
```

依赖方向是 `ase_layout.py` → `ase_assets.py` → `ase_localize.py` → `tool_reexport.py`。脚本按文件路径运行，不需要 pip 安装。改白名单、包布局或命令参数时，同时改对应的 `references/` 页面和本说明。

## 使用 Skill

将 `skills/ark-ase-localization` 整个目录复制到代理支持的 Skill 目录。以当前 Codex 为例，可使用用户级 `~/.agents/skills/ark-ase-localization`，或在目标工程内放置 `.agents/skills/ark-ase-localization`。目录中必须保留 `SKILL.md`、`scripts`、`references`。参见 [OpenAI 官方本地 Skill 文档](https://learn.chatgpt.com/docs/build-skills)。

然后向代理提出。按你手头的材料选一种说法即可：

```text
使用 $ark-ase-localization 汉化这个 ASE 模组。
模组 ID：2566418613
输入：D:\SteamLibrary\steamapps\workshop\content\346110\2566418613\WindowsNoEditor
请给出译文清单、未覆盖项、验证结果和可回滚覆盖补丁。
独立导出工具我没有，请把该项标为 not_run。不要安装到游戏目录。
```

```text
使用 $ark-ase-localization 检查这份已经解压的 ASE 模组。
输入：D:\mods\Example\WindowsNoEditor
先只做提取和审稿清单，列出 display_candidate 为 true 的显示字段，
以及不支持的文件。先不要写回。
```

`agents/openai.yaml` 只提供 Codex 的展示名和默认提示。复制整个目录时一并带上；真正执行依赖 `SKILL.md`、`scripts` 和 `references`。不同代理的发现目录可能不同。本仓库不依赖某个 MCP 插件或 API 密钥。只复制文件不代表代理已经加载成功；可显式提供 `SKILL.md` 路径。

## 不使用代理也能运行

Python 3.10+，仅标准库，无需 pip 安装。以下命令在 `skills/ark-ase-localization` 目录执行，路径应换成你自己的：

```bash
python scripts/ase_localize.py discover --id 2566418613 --library "/path/to/SteamLibrary"
python scripts/ase_localize.py unpack --input "/path/to/WindowsNoEditor" --output "./work/original"
python scripts/ase_localize.py extract --input "./work/original" --output "./work/plan.json"
```

若已经有解压后的原模组，可跳过 `unpack`，直接对那个副本 `extract`。`extract` 写出的记录没有 `translation`。审过并且 `display_candidate` 为 `true` 的项，只追加译文，原有字段保持不动：

```json
{
  "export_index": 0,
  "export_name": "Default__Example_C",
  "property_path": [0, 0],
  "key": "ModifierName",
  "kind": "StrProperty",
  "source": "Cold Aura",
  "display_candidate": true,
  "translation": "寒冷光环"
}
```

`display_candidate` 为 `false` 的记录，例如 `DinoNameTag`，留在清单里供审查，不要加 `translation`。脚本不会把未填写的英语自动翻成中文。同一条中文可以对应多条不同原文，回滚靠位置而不是靠“中文→英文”字典。

```bash
python scripts/ase_localize.py patch --input "./work/original" --plan "./work/plan.json" --output "./work/overlay"
python scripts/ase_localize.py verify --source "./work/original" --overlay "./work/overlay"
python scripts/ase_localize.py package --source "./work/original" --overlay "./work/overlay" --id 2566418613 --output "./work/patch.zip"
```

`patch` 在创建输出目录之前，会重新解析、定点读回，并按位置反向还原到与原件逐字节一致。覆盖目录里只有改过的 `.uasset` 和 `manifest.json`。

打包后的 ZIP 根上有 `manifest.json`、`verification.json` 和英文 `INSTALL.txt`，改过的资源在 `<模组 ID>/` 下面。包内没有 `.mod`。使用前需要已经安装完整原模组；这个命令本身不把文件写入游戏目录。

独立重导出可使用自行取得并确认版本的 UE4LocalizationsTool：

```bash
python scripts/tool_reexport.py --tool "/path/to/UE4localizationsTool.exe" --overlay "./work/overlay" --work "./work/tool-check"
```

它只在新副本上执行导出，不执行 import。缺失、失败或未读出项会明确列出并以非零状态退出。仓库不会下载工具或安装补丁到游戏目录。

独立导出通过后，可在 `package` 命令增加 `--reexport-report "./work/tool-check/reexport_report.json"`。工具会核对报告绑定的 manifest 和匹配数量；没有提供报告时，包内 `verification.json` 明确写为 `not_run`，不会暗示已通过独立导出。

## 命令约定

在 `skills/ark-ase-localization` 目录执行。下面的 `python` 指 Python 3.10 及以上；当前环境只有 `python3` 时，把命令里的 `python` 换成 `python3`。成功时结果打印到标准输出，编码会尽量设为 UTF-8。失败时退出码为 1，标准错误以 `ERROR:` 开头。

| 命令 | 参数 | 成功时能看到 | 需要换做法的情况 |
| --- | --- | --- | --- |
| `discover` | `--id` 必填；`--library` 可重复 | `mod_id`、`candidates`、`searched_libraries` | ID 含非数字会退出 1。一个候选都没有时仍退出 0，`candidates` 为 `[]` |
| `unpack` | `--input`、`--output` | `unpacked_files`、`source_modified: false`，以及输出目录里的 `source_manifest.json` | 没有 `.z`、压缩校验失败、输出已存在，或输出位于输入目录里面 |
| `extract` | `--input`、`--output` | `parsed_files`、`typed_strings`、`display_candidates`、`unsupported_files` | 输入下没有 `.uasset`，或计划文件已经存在 |
| `patch` | `--input`、`--plan`、`--output` | 覆盖目录和其中的 `manifest.json` | 哈希不一致、路径越界、没有实际改动的译文、反向还原不是逐字节一致 |
| `verify` | `--source`、`--overlay` | `verified_files`、`inverse_byte_verified: true`、`game_tested: false` | 覆盖目录里的资源和清单不一致，或哈希、反向还原失败 |
| `package` | `--source`、`--overlay`、`--id`、`--output`；可选 `--reexport-report` | `zip_verified`、压缩包 `sha256`、`files` | 报告和当前 manifest 不匹配，或目标 zip 已存在 |

`discover` 不传 `--library` 时，只在 Windows 上尝试读取当前用户的 Steam 注册表。传了库路径后不再读注册表，但会读取该库的 `steamapps/libraryfolders.vdf` 里带引号的 `path`，把其中成对反斜杠收成一条，再继续查找。它不扫描整盘，也不订阅、下载或启动游戏。

`candidates.kind` 只有两种：`installed`（`steamapps/common/ARK/ShooterGame/Content/Mods/<ID>`）和 `workshop-windows`（`steamapps/workshop/content/346110/<ID>/WindowsNoEditor`）。`LinuxNoEditor` 不会进入候选。

`unpack` 只接受 `.uasset.z` 和 `.umap.z`。旁边若有同名 `.uncompressed_size`，其中的数字必须等于解压后的字节数。它会先创建输出目录；只有标准输出里出现 `unpacked_files` 才算解压完成，中途失败留下的目录不能继续提取。`extract` 和 `patch` 只处理 `.uasset`；解压出来的 `.umap` 留在原件目录和 `source_manifest.json` 里，不会进入 `plan.json`。`patch` 在反向还原全部通过后才创建覆盖目录。

`unpack` 与 `patch` 的输出必须是还不存在的目录，并且不能放在输入目录里面。`extract` 和 `package` 只拒绝覆盖已有文件，请仍把 `plan.json` 和 zip 放在原件目录外面。

常见 `ERROR:` 句子和接下来该做什么，写在 [流程说明的命令拒绝一节](skills/ark-ase-localization/references/workflow.md#命令拒绝时)。

## 教程索引

- [完整操作流程](skills/ark-ase-localization/references/workflow.md)
- [两种实测资源布局与长度/偏移](skills/ark-ase-localization/references/ase-format.md)
- [Buff、FText、JSON 和运行时 UI](skills/ark-ase-localization/references/ui-and-json.md)
- [验证、统计、安装与发布](skills/ark-ase-localization/references/validation-and-release.md)
- [AG 起源与 Ark Nucleus 案例](skills/ark-ase-localization/references/case-studies.md)

## 开发与验证

从仓库根目录执行：

```bash
python -m unittest discover -s tests -v
```

测试运行时生成的样本是合成的包形数据，不是可装入游戏的资源。覆盖两种 profile、嵌套 Buff、FText 身份保持、数组文本、同译文碰撞、JSON 执行字段保护、缓存损坏、路径越界、源件哈希、覆盖包损坏和归档校验。

[验证记录](docs/VALIDATION.md)区分自动测试、代理应用测试、本地原件回归与游戏测试。**离线检查通过不代表游戏中的所有文字、布局和功能都已验证。**

## 支持边界

脚本实际接受的范围：

- 包头前缀、表位置和文件尾都符合已观察的 **402/7** 或 **404/10**。只看到相同版本号还不够，未知布局整文件保留。
- 显示文字位于已识别的 `StrProperty`、Base history 为 0 的 `TextProperty`，或 `DisplayNames` 的 FText 数组。属性嵌套超过 8 层会停止解析该导出。
- JSON 只处理白名单字段，并且只改允许的显示叶子。完整名单和 `display_candidate` 的判断在 [流程说明](skills/ark-ase-localization/references/workflow.md#可写字段)。
- 占位符自动检查只覆盖 `__0__` 这种 `__数字__`。其他格式标记靠审稿保留。
- `.uasset.z` / `.umap.z` 使用已观察的分块 zlib。`.umap` 解压后保留，不进入提取和写回。

以下内容保持原样并单独列出：ASA、其他 UE4/UE5 包、未知 FText 历史、任意 Struct/Array/Map、Kismet 字节码、图片里的文字、`LinuxNoEditor` 与 Windows 资源混用、`.mod`、内部名、`DinoNameTag`、权限、事件和绑定。原模组更新后重新提取并审稿，源件 SHA-256 必须与计划一致。

离线验证通过只说明这次写回可逆、哈希相符。它不代替游戏内的文字、换行、字体和按钮测试。没有独立导出工具时，归档中的状态是 `not_run`。

## 贡献与许可

欢迎用 [贡献指南](CONTRIBUTING.md) 提交新格式证据、术语修正和合成测试。默认不接收原模组资源或私人存档。

原创脚本、教程和合成测试以 [MIT](LICENSE) 发布。该许可不包含 ARK、第三方模组、第三方工具及其素材，也不改变它们各自的许可。
