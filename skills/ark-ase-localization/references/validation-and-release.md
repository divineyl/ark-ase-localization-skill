# 验证与覆盖包发布

## 五层证据

1. **来源**：源文件 SHA-256 与提取计划一致。版本变化或其他补丁造成哈希不同，先重新适配。
2. **结构**：写回后重新解析，定点读回译文，检查名称表、未修改 export、字段长度及偏移。
3. **反向还原**：用同一唯一位置将每条译文还原为各自原文，得到与源件逐字节一致的文件。两个原文译成同一中文时，不能使用“中文→英文”字典回滚。
4. **独立工具**：在专门的资源副本上重新导出，对照完整译文；保存工具版本、返回码、失败和未读出项。工具能导出文件不等于读出了每条译文。
5. **游戏验证**：进入物品、生物、Buff/HUD、制作、模态对话框和动态菜单；检查中文、截断、缺字、点击功能、管理员/普通玩家权限及重新加载。没有做就写“未进行游戏内测试”。

反向一致是窄范围写入的强验证，不证明翻译准确、字体正常或业务逻辑兼容。通用工具重序列化可能产生无法解释的额外差异，这时不能宣称已满足此方法的验证条件。

## UE4LocalizationsTool 的使用边界

工具不随本项目分发。记录实际使用的版本；下面是本项目曾用版本所支持的命令示例，其他版本先看帮助。

```text
UE4localizationsTool.exe exportall WORK_COPY OUTPUT.txt
UE4localizationsTool.exe export ONE_WORK_COPY.uasset -m2
```

`export` 可能在资源旁生成 `.txt`，所以只对新建的独立工作副本执行，不对游戏目录或不可变快照执行。标准导出和 M2 的读取覆盖不同，Buff 嵌套或长 JSON 需要逐项核查。

本仓库的 `tool_reexport.py` 是这条只读检查的入口。它不执行 `import`；报告字段和退出码见下面的覆盖包一节。

## 统计口径

`manifest.json` 的 `counts` 使用下面的键。口头统计要和这些键对上：

- `files`：实际被修改的 `.uasset` 数。
- `edited_properties`：属性、FText 或数组文字项的修改次数。一个 JSON 属性仍是一个资源字段。
- `translated_text_occurrences`：被修改的显示文本出现次数，包含 JSON 叶子。
- `json_text_occurrences`：语言表或配置里被修改的显示叶子出现次数。它已经包含在上一行里，两行不能相加。
- `unique_translation_pairs`：不同 `(原文, 译文)` 的数量，不是独立界面数量。

未覆盖项分开列出：不支持的文件或导出、未翻译的显示项、图片和代码常量、尚未运行的验证。例如 138 处状态/HUD 字段并不代表 138 个菜单，也不表示这整个模组只有 138 处 UI。

## 覆盖包

只包含已校验的改动资源和说明、清单、manifest。不要夹带 `.mod`、旧工具导出旁文件、完整原模组、用户存档、下载凭据或个人目录日志。

`package` 在创建 zip 之前重新验证来源、覆盖目录和可选报告。报告不匹配时不会留下新的 zip。归档写入后再检查 CRC，并按清单核对每个资源的 SHA-256。目标 zip 已存在时直接拒绝。附带 CLI 只做离线补丁，不安装进游戏。

压缩包里的路径是：

```text
<模组 ID>/<相对路径>.uasset
manifest.json
verification.json
INSTALL.txt
```

`manifest.json` 就是覆盖目录里的清单，含 `schema: 1`、`files`、`counts`、`allow_language_default`、`inverse_byte_verified`、`game_tested` 和 `installed`。后三项在这条命令里分别是 `true`、`false`、`false`。

`verification.json` 的形状：

```json
{
  "source_hashes_verified": true,
  "overlay_hashes_verified": true,
  "inverse_byte_verified": true,
  "independent_reexport": {"status": "not_run"},
  "game_tested": false,
  "installed": false
}
```

提供 `--reexport-report` 且通过时，`independent_reexport` 变为 `{"status": "passed", "matched_fields": <修改字段总数>}`。报告必须同时满足：`manifest_sha256` 等于当前 `overlay/manifest.json` 的 SHA-256，`failures` 和 `missing` 都是空数组，`matched_fields` 等于清单里全部 `edits` 的条数。`INSTALL.txt` 是英文安装提示，并写明独立导出状态；其中的 “Game UI has not been tested.” 保持为未做游戏测试。

`tool_reexport.py` 把覆盖资源复制到新的 `--work` 目录，对每个资源运行 `export <副本> -m2`，单文件超时 30 秒。导出文本里的换行会先看成 `<lf>` 再和译文比较。工具若改动了副本，检查失败。报告写到 `work/reexport_report.json`，包含 `manifest_sha256`、`matched_fields`、`missing`、`failures`、`game_tested: false`，以及说明本次只做副本导出的 `scope`。有缺失或失败时进程退出码为 1，报告仍然写出。未捕获的参数或哈希错误会直接抛出，此时不要把半成品目录当作通过。这条路线没有 `import`。

如果用户要求安装：先确认游戏与服务器均退出；校验现装资源必须与源件或本补丁哈希匹配；完整备份将覆盖的文件，备份校验通过后再写入；完成后逐个核对输出哈希。失败恢复自己的备份，不删除存档或其他模组。

PowerShell 安装脚本要在实际目标宿主中测试：`pwsh` 可用不代表 `powershell.exe` 的模块环境相同。本次实践遇到旧宿主找不到 `Get-FileHash`，改用 .NET SHA256 后完成隔离副本测试。不要把宿主差异误认为模组文件损坏。

## 开源与贡献

本仓库仅提供原创教程、解析/写入脚本和合成测试。不附带模组资产和第三方工具。发布自己的汉化资源包前，核对原模组作者允许的分发形式；教程开源不会自动改变原资源授权。

提交新 profile 或字段支持时，应附：去个人信息的格式证据、完整结构约束、能复现问题的合成样本、失败到通过的测试、反向还原结果及独立读回结果。不能仅凭“游戏这次没崩”放宽结构检查。
