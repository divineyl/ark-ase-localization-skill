# Buff、UMG、FText 与 JSON 界面

## 先按文字来源分类

物品和生物常使用 `DescriptiveNameBase`、`ItemDescription`、`DescriptiveName`、`DinoDescriptiveName`。制作界面可能使用 `InventoryNameOverride` 和 `RemoteInventoryDescriptionString`。状态栏另有 `ModifierName`、`ModifierDescription`、`HUDMessage`。

UMG 不只存于 `Default__`：控件实例、WidgetTree 和枚举显示文本也可能含译文。只处理类默认对象会漏掉按钮、对话框、加载提示和枚举标签。

同一个词可能位于默认对象和控件实例中，应按资源位置分别处理，并在统计中明确出现次数，不以唯一文本数代替实际修改字段数。

## FText

本脚本只支持 Base history `0`：flags 4 字节、history 1 字节，然后为 namespace、key、source 三个 FString。翻译 source，保留 flags、history、namespace、key。禁止把命名空间或 GUID 一起改成中文。

不能将此布局套到所有 FText。格式化文本、数字、字符串表引用、其他 history 需要单独解析；遇到不支持项保留并记录。`DisplayNames` 的 FText 数组有数量前缀，每项仍须单独解析并保留键。

运行时本地化资源、旧用户存档和动态赋值可能覆盖控件默认值。文件里已经有中文并不能证明玩家看到的就是中文。

## JSON：翻译值，保留执行含义

安全的例子：

```json
{
  "NLLabel": "生成",
  "EventUID": "Nucleus/Spawn",
  "BindValue": "Health",
  "Permission": "Nucleus_SpawnDinos",
  "Min": 1
}
```

`NLLabel` 是直接显示文字时可以翻译。`EventUID`、`BindValue`、`Permission`、资源路径、数值、枚举 ID、数据源名称、控件类别和 JSON 键本身保持原值。

但 `"NLLabel":"_SPAWN_IN_FRONT_"` 是查表 token，不是显示英语。保留 token，翻译语言表中的对应值。有些原版 token 缺少末尾下划线，不要仅用完整首尾下划线判断。

下拉框的 `Name` 只有在它是带 `EnumID` 的显示项时才可改；权限组名称、DataSource.Name 等不能见到 Name 就翻译。应递归比较修改前后 JSON，确保非显示叶子、键集合、数组顺序和类型不变。

附带脚本对白名单 JSON 字段进行结构比较。新增 schema 需要先给出字段语义和测试，不能用“关闭所有 JSON 验证”绕过。

## Nucleus 语言表

实测使用：

```json
{
  "LStrings": [
    {"Key":"_YES_", "EN":"Yes", "ZH":"是"}
  ]
}
```

保留 `EN` 和 `Key`，添加/更新 `ZH`。不要为快速显示中文而把整个英文语言表替换掉。用户未必选择了 ZH，已有客户端设置也可能保留 EN；安装说明必须告诉用户选择“中文 / ZH”。

如果用户选择让新配置默认中文，可以在计划顶层显式设置 `allow_language_default: true`，只改变 `MOD_ClientSettings.CoreClientSettings.Language` 的 EN/ZH；脚本不会因此改动其他设置、权限或已有存档。

原表可能重复使用 Key。先按具体源条目和绑定分析，不能在字典去重后无声丢失一条。缺失 token 的新增需要单独审阅，附带写入器默认保持原有语言项数量，避免在“翻译”中悄悄新增运行内容。

### 语言键直接显示时的排查

1. 先核对实际启动目录和已安装资源哈希；重启游戏后，分别在 Nucleus 选择 ZH 和 EN。如果两种语言都显示 `_YES_` 之类的键名，检查整个查表链，而不只检查 ZH 翻译。旧截图应与新截图区分，文件校验不代替游戏内验证。
2. 查调用方传入的键、键的规范化规则、语言表中的 `Key`、表加载结果和用户自定义译文的合并顺序。特别留意游戏本身的本地化资源是否把蓝图中作为 JSON 字段名的可本地化字符串意外转换了。该可能性必须结合资源、字节码和运行表现验证，不能仅凭症状断言。
3. Ark Nucleus 0.101.0 的一次实测中，游戏中文 `GraphLiteral` 把内部字段名 `Key` 映射为“键”，而语言表 JSON 字段仍是 `Key`。该案例修复了模组内 7 个资源的 22 处相关可本地化字面量身份；修复后用户截图显示 ZH 和 EN 的图鉴标题与按钮正常。此结果支持该案例的冲突诊断，但不代表所有未解析键都有相同原因。
4. 当显示短句仍为英文，先查调用方式。例如 `Can be tames:` 经过该版本 `Nucleus_GenerateLocalizationKey` 去空格后查询 `Canbetames:`；表中没有这一项。增加经过审阅的 `EN` 和 `ZH` 条目后，用户确认中文显示“可驯服：”。键的规范化规则必须针对实际版本核对，不要照搬到其他模组。

本仓库通用脚本**不支持 Kismet 字节码写入**。上面的模组专用修复是有风险的个案，不提供自动修改命令，也不是更改全部 `Key`、替换任意文本或修改全局游戏语言文件的建议。分析字节码时，必须定位具体执行位置，在副本上检查脚本结构、跳转、未改数据和可逆性，安装前备份并校验版本，再在游戏中验证；没有足够证据时保留原件。动态生成的 `Region #`、其他模组的生物名称和颜色名称并不因此自动汉化。

[Ark Nucleus 原作者的源文件仓库](https://github.com/ArkNucleus/ASE-OpenSourceNucleus)可用于研究其本地化和动态界面系统。它与本教程的原创脚本不是同一授权范围，未被打包进本仓库。

## 其他常见英文来源

- 另一个模组提供的生物/物品名称：由提供者的显示字段决定。
- 扫描器读取 `DinoNameTag`：保护内部标识，必要时研究扫描器自己的显示映射。
- Kismet 字符串常量：不能按普通 FString 改长度；涉及脚本字节码长度和跳转，当前脚本不处理。
- 图片中的英文：需要独立纹理处理及资源验证，不属于文字字段补丁。
- 自定义字体缺字或框太窄：在游戏里确认字体回退和布局；不能用离线文本验证替代。
- 缓存和用户译文优先级：先切换正确语言、重进界面再查原因，不自动删除用户存档。
