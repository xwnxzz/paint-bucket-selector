# -*- coding: utf-8 -*-
"""Blender 5.3 API 探针：确认本版本可用接口差异。"""
import bpy
import bmesh
import sys

print("=== VERSION ===", bpy.app.version_string)

print("=== bpy.context mouse attrs ===")
print([a for a in dir(bpy.context) if "mouse" in a.lower()])
print("region:", getattr(bpy.context, "region", None))
print("region_data:", getattr(bpy.context, "region_data", None))

print("=== material color API ===")
mat = bpy.data.materials.new("probe")
mat.use_nodes = True
print("diffuse_color:", tuple(mat.diffuse_color))
nt = mat.node_tree
bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
print("principled:", bsdf)
if bsdf:
    print("inputs:", [i.name for i in bsdf.inputs][:12])
    print("base color:", tuple(bsdf.inputs["Base Color"].default_value))

print("=== bmesh layers ===")
me = bpy.data.meshes.new("m")
bm = bmesh.new()
print("loop layers color:", hasattr(bm.loops.layers, "color"))
print("loop layers float_color:", hasattr(bm.loops.layers, "float_color"))
print("verts layers float_color:", hasattr(bm.verts.layers, "float_color"))
bm.free()

print("=== color attributes ===")
print("mesh.color_attributes:", me.color_attributes)
print("types:", [i for i in dir(bpy.types) if i.startswith("PaintBucket")][:5])
print("ops available:", "paint_bucket.select_same_material" in dir(bpy.ops.paint_bucket) if hasattr(bpy.ops, "paint_bucket") else False)

print("=== tool settings ===")
print("mesh_select_mode:", bpy.context.tool_settings.mesh_select_mode)

print("=== python ===", sys.version)
