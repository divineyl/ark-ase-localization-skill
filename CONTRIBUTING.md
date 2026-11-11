# 贡献指南

请让改动可以被别人复现，而不是只描述“我这台机器上可以”。

## 新资源格式或新字段

1. 提供游戏类型、平台、对象版本、licensee、表结构证据和失败类型。
2. 用脚本生成最小合成样本，先展示现有实现失败，再实现支持。
3. 明确哪些字节可改，哪些未知数据必须保留；不要仅放宽版本号或边界检查。
4. 运行完整测试，并提供源件哈希检查、定点读回、按位置反向一致和独立工具结果。
5. 若仅本地有真实资源，报告统计和结果即可，不提交资源二进制。

## 翻译和教程

说明术语所属模组与上下文。UI、物品、描述和内部标识应分开判断。不要把个人译法变成全部模组的强制规则。改正数字、占位符或执行语义时附上原文证据。

## 不提交的内容

- 原模组 `.uasset`、`.umap`、`.mod`、`.z`、纹理、音频或第三方工具 `.exe`。
- 用户存档、聊天记录、Steam ID、API 密钥、Cookie、真实用户目录或机器上的完整日志。
- 无来源的大段第三方代码；参考第三方项目应链接并遵守其许可。

## 改哪一个文件

行为以 `skills/ark-ase-localization/scripts/` 为准，说明和技能要跟着改。

| 要改的行为 | 代码 | 同时更新 |
| --- | --- | --- |
| 包头、表宽度、属性递归 | `scripts/ase_layout.py` | `references/ase-format.md`、`tests/fixtures.py` |
| 可写字段、JSON 叶子、`.z` 解压 | `scripts/ase_assets.py` | `references/workflow.md` 的可写字段、`references/ui-and-json.md` |
| 命令参数、计划、归档 | `scripts/ase_localize.py` | `README.md` 的命令表、`SKILL.md` 的脚本入口、`references/validation-and-release.md` |
| 外部工具只读导出 | `scripts/tool_reexport.py` | `references/validation-and-release.md` |
| 代理何时启用、交付什么 | `SKILL.md` | `agents/openai.yaml` 的默认提示保持同一边界 |

`ase_layout.py` 不导入其他脚本。`ase_assets.py` 使用布局和白名单，`ase_localize.py` 组织命令，`tool_reexport.py` 只复用命令脚本里的路径和摘要函数。测试从 `tests/fixtures.py` 生成合成包，不读取游戏文件。

## 提交前

运行 `python -m unittest discover -s tests -v`。检查 Markdown 相对链接、UTF-8 编码、Skill 名称和 frontmatter。`SKILL.md` 的 `description` 保持在 1024 字符以内，并写明 ASE 与不适用的 ASA。说明是否做过独立导出或游戏验证，没做的不要写成通过。
