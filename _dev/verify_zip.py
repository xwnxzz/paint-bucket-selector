# -*- coding: utf-8 -*-
"""验证打包后的 zip：清单字段、解包导入、注册/注销闭环。

运行：blender -b --factory-startup --python _dev/verify_zip.py
"""

import os
import shutil
import sys
import tempfile
import tomllib
import zipfile

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIP = os.path.join(ROOT, "dist", "paint_bucket_selector-1.0.0.zip")

FAILS = []


def check(name, condition, detail=""):
    print(f"[{'PASS' if condition else 'FAIL'}] {name}" + (f" | {detail}" if detail else ""))
    if not condition:
        FAILS.append(name)


check("zip 存在", os.path.isfile(ZIP), ZIP)
with zipfile.ZipFile(ZIP) as archive:
    names = sorted(archive.namelist())
    manifest_raw = archive.read("blender_manifest.toml").decode("utf-8")

check(
    "zip 仅含 5 个插件文件",
    names == ["__init__.py", "blender_manifest.toml", "operators.py", "panel.py", "properties.py"],
    str(names),
)

manifest = tomllib.loads(manifest_raw)
check("清单 id 合法（小写无点）", manifest.get("id") == "paint_bucket_selector", str(manifest.get("id")))
check("清单名称中文正确", manifest.get("name") == "油漆桶选择", str(manifest.get("name")))
check("最低版本为 4.2.0", manifest.get("blender_version_min") == "4.2.0", str(manifest.get("blender_version_min")))
check("类型为 add-on", manifest.get("type") == "add-on", str(manifest.get("type")))

TMP = tempfile.mkdtemp(prefix="paint_bucket_zip_")
PKG = os.path.join(TMP, "paint_bucket_selector")
os.makedirs(PKG)
try:
    with zipfile.ZipFile(ZIP) as archive:
        archive.extractall(PKG)
    sys.path.insert(0, TMP)
    import paint_bucket_selector as packaged  # noqa: E402

    check("解包后可作为包导入", hasattr(packaged, "register"), packaged.__file__)
    packaged.register()
    check("打包副本注册成功", hasattr(bpy.types.Scene, "paint_bucket"))
    check(
        "打包副本生成操作符",
        hasattr(bpy.ops.paint_bucket, "select_same_material"),
    )
    bpy.context.scene.paint_bucket.tolerance = 0.25
    check("打包副本属性可写", abs(bpy.context.scene.paint_bucket.tolerance - 0.25) < 1e-6)
    packaged.unregister()
    check("打包副本注销后属性移除", not hasattr(bpy.types.Scene, "paint_bucket"))
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("\n===== 打包验证:", "全部通过" if not FAILS else f"失败 {len(FAILS)} 项", "=====")
if FAILS:
    sys.exit(1)
