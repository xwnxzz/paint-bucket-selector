# -*- coding: utf-8 -*-
"""注册与属性探针：确认 5.3 下属性组、操作符 RNA 与面板可用。"""

import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(ROOT))

import paint_bucket_selector as addon  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
addon.register()

scene = bpy.context.scene
settings = scene.paint_bucket
props = settings.bl_rna.properties
print("=== SCENE PROPS ===")
print(sorted(props.keys()))
print("tolerance:", props["tolerance"].default, props["tolerance"].hard_min, props["tolerance"].hard_max)
print("seed items:", [item.identifier for item in props["seed_source"].enum_items])
print("match items:", [item.identifier for item in props["match_mode"].enum_items])

print("=== OPERATOR RNA ===")
rna = bpy.ops.paint_bucket.select_by_color.get_rna_type()
print("op props:", sorted(rna.properties.keys()))
print("tolerance min:", rna.properties["tolerance"].hard_min)
print("selection items:", [item.identifier for item in rna.properties["selection_mode"].enum_items])
print("rna name:", getattr(rna, "name", None), "|", getattr(rna, "description", None))

print("=== PANEL CLASS EXPOSURE ===")
print("bpy.types has panel:", hasattr(bpy.types, "PAINTBUCKET_PT_main"))
print("bpy.types has settings:", hasattr(bpy.types, "PAINTBUCKET_PG_settings"))
print("scene pointer type:", type(settings).__name__)

print("=== OPS CALLABLE (object mode) ===")
bpy.ops.mesh.primitive_cube_add()
print(bpy.ops.paint_bucket.select_same_material('EXEC_DEFAULT'))
print("last_result:", scene.paint_bucket.last_result)

print("=== UNREGISTER / REREGISTER ===")
addon.unregister()
print("after unregister, scene prop:", hasattr(scene, "paint_bucket"))
addon.register()
print("after re-register, scene prop:", hasattr(bpy.context.scene, "paint_bucket"))
addon.unregister()
addon.register()
print("double cycle ok")
print("RESULT OK")
