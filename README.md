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

## 使用 Skill

将 `skills/ark-ase-localization` 整个目录复制到代理支持的 Skill 目录。以当前 Codex 为例，可使用用户级 `~/.agents/skills/ark-ase-localization`，或在目标工程内放置 `.agents/skills/ark-ase-localization`。目录中必须保留 `SKILL.md`、`scripts`、`references`。参见 [OpenAI 官方本地 Skill 文档](https://learn.chatgpt.com/docs/build-skills)。

然后向代理提出：

```text
使用 $ark-ase-localization 汉化这个 ASE 模组。
模组 ID：你要处理的工坊 ID
输入目录：你的 Windows 模组资源或 WindowsNoEditor 缓存目录
请提供译文清单、未覆盖项、验证结果和覆盖补丁。
```

不同代理的发现目录可能不同；本仓库的 Skill 使用标准目录结构，不依赖某个 MCP 插件或 API 密钥。只复制文件不代表代理已经加载成功；可显式提供 `SKILL.md` 路径。

## 不使用代理也能运行

Python 3.10+，仅标准库，无需 pip 安装。以下命令在 `skills/ark-ase-localization` 目录执行，路径应换成你自己的：

```bash
python scripts/ase_localize.py discover --id 2566418613 --library "/path/to/SteamLibrary"
python scripts/ase_localize.py unpack --input "/path/to/WindowsNoEditor" --output "./work/original"
python scripts/ase_localize.py extract --input "./work/original" --output "./work/plan.json"
```

若已经有解压后的原模组，可跳过 `unpack`。编辑 `plan.json`，为确定要修改的显示记录增加 `translation`，保持原件哈希、定位信息和原文不变。脚本不自动把所有英语翻成中文。

```bash
python scripts/ase_localize.py patch --input "./work/original" --plan "./work/plan.json" --output "./work/overlay"
python scripts/ase_localize.py verify --source "./work/original" --overlay "./work/overlay"
python scripts/ase_localize.py package --source "./work/original" --overlay "./work/overlay" --id 2566418613 --output "./work/patch.zip"
```

输出路径必须是新路径；脚本拒绝覆盖已有文件或目录。`patch` 在写出前完成全部目标的解析、读回和按位置反向还原验证。打包后的 ZIP 包含 ID 文件夹和说明；需要先安装完整原模组。

独立重导出可使用自行取得并确认版本的 UE4LocalizationsTool：

```bash
python scripts/tool_reexport.py --tool "/path/to/UE4localizationsTool.exe" --overlay "./work/overlay" --work "./work/tool-check"
```

它只在新副本上执行导出，不执行 import。缺失、失败或未读出项会明确列出并以非零状态退出。仓库不会下载工具或安装补丁到游戏目录。

独立导出通过后，可在 `package` 命令增加 `--reexport-report "./work/tool-check/reexport_report.json"`。工具会核对报告绑定的 manifest 和匹配数量；没有提供报告时，包内 `verification.json` 明确写为 `not_run`，不会暗示已通过独立导出。

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

不处理任意 UE4/UE5 包、ASA、未知 FText 历史、任意嵌套结构、字节码跳转、图片中的文字或跨平台资源改写。原模组更新后要重新提取并审稿；不要跳过源件哈希校验。默认保留 `.mod`、内部名称、DinoNameTag、权限、事件与绑定。

## 贡献与许可

欢迎用 [贡献指南](CONTRIBUTING.md) 提交新格式证据、术语修正和合成测试。默认不接收原模组资源或私人存档。

原创脚本、教程和合成测试以 [MIT](LICENSE) 发布。该许可不包含 ARK、第三方模组、第三方工具及其素材，也不改变它们各自的许可。
