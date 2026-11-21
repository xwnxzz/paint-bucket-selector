# 油漆桶选择 · Paint Bucket Selector

> Blender 扩展：编辑模式下一键选中与种子面**同材质或同颜色**的整块面 —— 像油漆桶一样刷选择。

- 中文界面，面板在 3D 视图侧栏 `N` → **油漆桶**
- 面 / 边 / 顶点三种选择模式通用
- 材质槽匹配、颜色容差匹配、连通区洪水填充、加选减选反选、相邻扩展
- 纯 `bmesh` 实现，不依赖 `bpy.ops.mesh.select_similar`，多对象同时编辑也正常
- 兼容 Blender **4.2+**（在 5.3.0 上实测 48 项用例全通过）

## 安装

**方式一（推荐）**：`编辑 > 偏好设置 > 获取扩展` → 右上角下拉菜单 → `从磁盘安装` → 选 `dist/paint_bucket_selector-1.0.0.zip` → 启用「油漆桶选择」。

**方式二（源码）**：把 `__init__.py`、`operators.py`、`panel.py`、`properties.py`、`blender_manifest.toml` 放进

```
%APPDATA%\Blender Foundation\Blender\<版本>\extensions\user_default\paint_bucket_selector\
```

重启 Blender 后启用。

## 使用

1. 选中网格对象，`Tab` 进编辑模式（面/边/顶点都行）。
2. 点一块面作为**种子**；或把「种子来源」切到 **鼠标悬停面**，直接照鼠标下的面刷。
3. 按需要点按钮：

| 按钮 | 行为 |
|---|---|
| 选择同材质面 | 全网格匹配同材质面，**不要求相连** |
| 选择相连同材质区 | 从种子沿共享边洪水填充，只选连成一片的那块（真正的油漆桶） |
| 加选 / 减选 | 对当前选择做并集 / 差集 |
| 按颜色相近选择 | 忽略材质槽，只比颜色（无材质时回退面颜色层） |
| 加选相邻同材质面 | 当前选择向外扩一圈 |
| 反选同材质 | 同材质的面取反 |

参数：

- **种子来源**：`激活面`（最后点选的面）/ `鼠标悬停面`（取不到时自动回退激活面）
- **匹配依据**：`材质槽` / `槽或颜色` / `仅颜色`
- **颜色容差**：RGB 欧氏距离阈值，`0` 表示完全一致（默认 `0.08`）

面板底部「最近结果」会写清本次匹配情况，例如 `立方体：激活面 匹配 2 个面，当前选中 2 个（M1）`。

对象模式误点按钮 → 状态栏提示「请先进入编辑模式（Tab）后再使用油漆桶选择」，不会崩。

## 与内置算子对比

| | 内置 `mesh.select_similar(FACE_MATERIAL)` | 本插件 |
|---|---|---|
| 同材质全选 | ✅ | ✅ 结果逐面一致 |
| 连通区（油漆桶） | 需再叠 `select_linked` | ✅ 一步 |
| 颜色容差匹配 | ❌ | ✅ |
| 无材质面回退面颜色 | ❌ | ✅ |
| 加选 / 减选 / 反选 / 相邻扩展 | 需多次操作 | ✅ 按钮直出 |
| 多对象同时编辑 | 受限 | ✅ 逐个对象处理 |

实测对拍：三材质立方体种子取 M1 面，本插件 `[2, 3]`，内置算子 `[2, 3]`，完全一致。

## 已知边界

- **悬停取面**用 `scene.ray_cast`，得到的是*评估后网格*的面索引。对象挂 Boolean / Decimate 这类改拓扑的修改器时索引可能与原始网格错位 —— 这类对象请用「激活面」种子。
- 悬停需要真实 3D 视图区域；无头/无视图时自动回退激活面并在状态栏提示，不会静默失败。
- 颜色比较用的是材质的**视图颜色**（`diffuse_color`），不是节点树最终渲染色。要按贴图选区，请用 UV/材质槽维度。

## 开发与打包

```bash
BLENDER="/c/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe"

"$BLENDER" -b --factory-startup --python _dev/test_addon.py   # 48 项功能断言
"$BLENDER" -b --factory-startup --python _dev/verify_zip.py   # 打包内容 + 注册闭环
```

打包（`_dev` 与 README 不进安装包）：

```bash
mkdir -p dist/_stage
cp __init__.py operators.py panel.py properties.py blender_manifest.toml dist/_stage/
"$BLENDER" -b --factory-startup --command extension build \
  --source-dir "$PWD/dist/_stage" --output-dir "$PWD/dist"
rm -rf dist/_stage
"$BLENDER" -b --factory-startup --command extension validate "$PWD/dist/paint_bucket_selector-1.0.0.zip"
```

> 清单里写 `[build] paths` 会让 Blender 5.3 的 `extension build` 报 `missing "__init__.*"`，所以采用暂存目录方式，不写 `[build]` 段。

## 结构

```
paint_bucket_selector/
├── __init__.py             # 注册入口：properties → operators → panel
├── operators.py            # bmesh 选面核心：种子、材质/颜色匹配、洪水填充、相邻扩展
├── panel.py                # 3D 视图侧栏中文面板
├── properties.py           # Scene 属性组（种子来源/匹配依据/容差/最近结果）
├── blender_manifest.toml   # 扩展清单
├── _dev/                   # 测试与打包验证脚本（不打包）
└── dist/                   # 构建产物
```

## 许可

GPL-3.0-or-later，见 [LICENSE](LICENSE)。
