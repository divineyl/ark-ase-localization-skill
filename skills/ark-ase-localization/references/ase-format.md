# 两种实测 ASE 资源布局

以下为本项目在指定样本中观察并验证的布局，不是对所有 ASE/UE4 文件的通用格式承诺。偏移从文件开头计，整数为 little-endian。脚本同时验证完整头前缀、文件夹、表位置、记录宽度、导出范围、bulk 与尾标记。

## Profile 402/7

- 前 24 字节：`c1832a9efdffffff60030000920100000700000000000000`。
- legacy `-3`，UE3 版本 `864`，对象版本 `402`，licensee `7`，custom versions 数量 `0`。
- 名称表开始：`163`；bulk 起点字段：`147`，类型 int64。

## Profile 404/10

- 前 24 字节：`c1832a9efdffffff60030000940100000a00000000000000`。
- legacy `-3`，UE3 版本 `864`，对象版本 `404`，licensee `10`，custom versions 数量 `0`。
- 名称表开始：`171`；bulk 起点字段：`155`，类型 int64。

## 两者在本实现中的共同约束

- `24`：header size，int32。
- `28`：FString 文件夹，必须为 `None` 且结束于 `37`。
- `41`：连续 7 个 int32，依次是 name count/offset、export count/offset、import count/offset、depends offset。
- 名称是 FString 序列，本布局无额外名称哈希。
- import 记录 `28` 字节；export 记录 `68` 字节。
- export 记录内 `+12` 为名称索引，`+24/+28` 为 serial size/offset，均为 int32。
- 文件尾 4 字节为 `c1832a9e`。
- 这里只接受 bulk 起点为 `0` 或 `文件长度 - 4`；有外部数据/嵌入 bulk 的网格、纹理和音频常被拒绝，它们不是文字覆盖的默认目标。

标准属性 tag 为名称 FName 8 + 类型 FName 8 + 数据长度 4 + array index 4，另有 Bool 1、Byte 8、Struct 8、Array 8 字节的附加头。这些都是本布局的规则，不适用于任意新 UE4/UE5 序列化版本。

## FString

int32 长度为正时按单字节字符计（包含 NUL），为负时按 UTF-16 code unit 计（包含终止符），不是按 Python 字符数计。中文写入使用 UTF-16LE。长度变化后需要更新所在属性、外层结构、export size、后续 export offset 和对应 profile 的 bulk 起点。

现有读取器对正长度字段采用 CP1252，对负长度字段采用 UTF-16LE；非 ASCII 的单字节来源不能据此推定原始编码。若反向重编码无法逐字节恢复，当前写入路线会拒绝该改动。不要通过忽略解码错误来继续修改。

## 为什么标准导出会漏 Buff

状态名称与说明可位于 `BuffDescription` StructProperty，结构类型为 `StatusValueModifierDescription`。其内部 `ModifierName` / `ModifierDescription` 才是显示字符串。某些工具按较新 Struct 头宽度读取，会在旧资源中错位或跳过它。

本脚本只对这一已证实结构递归。未知 Struct、Map、其他 Array 保留原 payload，不扫描其中的“看起来像字符串”的字节来写回。

## 最小修改原则

重建目标导出块的已识别属性及其原始尾部。名称表、import、未修改的属性 payload、未知尾部和其他 export 均保留；只调整有证据需要调整的长度/偏移字段。

没有原文匹配、遇到未知 profile、范围不合法、缺尾标记、未知 FText 历史或反向验证失败时，停止该资源写回。不要修改版本号来强迫解析，也不要用同长度中文替换或任意空字节填充来规避偏移问题。

## 进一步研究的原始资料

- [UEViewer 的 Unreal 包头读取实现](https://github.com/gildor2/UEViewer/blob/master/Unreal/UnrealPackage/UnPackage4.cpp)：用于对照版本分支和包结构。
- [UAssetAPI 项目](https://github.com/atenfyr/UAssetAPI)：可对照属性、FText 和 Kismet 的序列化概念；不代表其每个版本都支持这些 ASE 样本。

本仓库不内置上述项目的代码或二进制；这里的固定 profile 依据本项目样本验证，换样本仍须重新检查。
