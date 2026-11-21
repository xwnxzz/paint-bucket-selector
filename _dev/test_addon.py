# -*- coding: utf-8 -*-
"""无头验证：注册、属性、bmesh 选面结果（立方体 / UV 球 / 无材质色带）。

运行：blender -b --factory-startup --python _dev/test_addon.py
失败时以非零退出码结束，便于批处理判断。
"""

import os
import sys
import types

import bmesh
import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(ROOT))

import paint_bucket_selector as addon  # noqa: E402

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" | {detail}" if detail else ""))
    return bool(condition)


def approx(value, target, eps=1e-5):
    return abs(value - target) <= eps


# --------------------------------------------------------------------------
# 场景工具
# --------------------------------------------------------------------------
def reset_file():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def make_material(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
    return mat


def make_cube(name="测试立方体"):
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 0.0))
    obj = bpy.context.object
    obj.name = name
    return obj


def face_by_normal(obj, axis, sign):
    for poly in obj.data.polygons:
        if abs(poly.normal[axis] - sign) < 0.5:
            return poly.index
    raise RuntimeError(f"找不到法线 {axis}/{sign} 的面")


def enter_edit(obj, mode='FACE'):
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for other in list(bpy.context.selected_objects):
        other.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    flags = {
        'FACE': (False, False, True),
        'EDGE': (False, True, False),
        'VERT': (True, False, False),
    }
    bpy.context.tool_settings.mesh_select_mode = flags[mode]


def exit_edit():
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def clear_selection(bm):
    for face in bm.faces:
        face.select = False
    for edge in bm.edges:
        edge.select = False
    for vert in bm.verts:
        vert.select = False


def seed_face(obj, face_index):
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    clear_selection(bm)
    face = bm.faces[face_index]
    face.select = True
    for edge in face.edges:
        edge.select = True
    for vert in face.verts:
        vert.select = True
    bm.faces.active = face
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)


def edit_selected_faces(obj):
    bm = bmesh.from_edit_mesh(obj.data)
    return {face.index for face in bm.faces if face.select}


def edit_selected_verts(obj):
    bm = bmesh.from_edit_mesh(obj.data)
    return {vert.index for vert in bm.verts if vert.select}


def edit_selected_edges(obj):
    bm = bmesh.from_edit_mesh(obj.data)
    return {edge.index for edge in bm.edges if edge.select}


def object_selected_faces(obj):
    return {poly.index for poly in obj.data.polygons if poly.select}


def object_selected_verts(obj):
    return {vert.index for vert in obj.data.vertices if vert.select}


def object_selected_edges(obj):
    return {edge.index for edge in obj.data.edges if edge.select}


def run_op(name, **kwargs):
    return getattr(bpy.ops.paint_bucket, name)(**kwargs)


def set_scene(match_mode=None, tolerance=None, seed_source=None):
    settings = bpy.context.scene.paint_bucket
    if match_mode is not None:
        settings.match_mode = match_mode
    if tolerance is not None:
        settings.tolerance = tolerance
    if seed_source is not None:
        settings.seed_source = seed_source


# --------------------------------------------------------------------------
# 1. 注册 / RNA
# --------------------------------------------------------------------------
def test_registration():
    scene = bpy.context.scene
    check("Scene 上存在 paint_bucket 属性组", hasattr(scene, "paint_bucket"))
    if not hasattr(scene, "paint_bucket"):
        return
    settings = scene.paint_bucket
    prop_keys = set(settings.bl_rna.properties.keys())
    expected = {"seed_source", "match_mode", "tolerance", "last_result"}
    check("属性组字段齐全", expected.issubset(prop_keys), f"实际 {sorted(prop_keys)}")

    tolerance_prop = settings.bl_rna.properties["tolerance"]
    check(
        "容差范围 0..1 且默认 0.08",
        approx(tolerance_prop.hard_min, 0.0) and approx(tolerance_prop.hard_max, 1.0),
        f"min={tolerance_prop.hard_min} max={tolerance_prop.hard_max} default={tolerance_prop.default}",
    )

    rna = bpy.ops.paint_bucket.select_by_color.get_rna_type()
    check("操作符 RNA 可读", "selection_mode" in rna.properties and "tolerance" in rna.properties)
    check(
        "选择方式枚举为替换/加选/减选",
        [item.identifier for item in rna.properties["selection_mode"].enum_items]
        == ["REPLACE", "ADD", "SUBTRACT"],
    )

    panel_exposed = hasattr(bpy.types, "PAINTBUCKET_PT_main")
    print(f"[INFO] bpy.types 是否暴露面板类: {panel_exposed}（5.3 可不暴露，不影响使用）")
    panel_cls = getattr(bpy.types, "PAINTBUCKET_PT_main", None)
    if panel_cls is not None:
        check(
            "面板位于 3D 视图侧栏且中文分类",
            panel_cls.bl_space_type == 'VIEW_3D'
            and panel_cls.bl_region_type == 'UI'
            and panel_cls.bl_category == "油漆桶",
            f"{panel_cls.bl_space_type}/{panel_cls.bl_region_type}/{panel_cls.bl_category}",
        )
    check("操作符标签为中文", any("\u4e00" <= ch <= "\u9fff" for ch in rna.name), rna.name)

    # 完整注销 / 重注册循环
    addon.unregister()
    check("注销后 Scene 属性被移除", not hasattr(bpy.context.scene, "paint_bucket"))
    addon.register()
    addon.unregister()
    addon.register()
    check("两次注销/重注册无异常", hasattr(bpy.context.scene, "paint_bucket"))


# --------------------------------------------------------------------------
# 2. 立方体：同材质 / 相连 / 相邻 / 反选
# --------------------------------------------------------------------------
def build_material_cube():
    obj = make_cube()
    red = make_material("红漆", (0.8, 0.05, 0.05))
    green = make_material("绿漆", (0.05, 0.7, 0.1))
    obj.data.materials.append(red)
    obj.data.materials.append(green)

    plus_x = face_by_normal(obj, 0, 1.0)
    minus_x = face_by_normal(obj, 0, -1.0)
    same = {plus_x, minus_x}
    for poly in obj.data.polygons:
        poly.material_index = 0 if poly.index in same else 1
    return obj, same, {poly.index for poly in obj.data.polygons} - same


def test_material_cube():
    set_scene(match_mode='SLOT', tolerance=0.08, seed_source='ACTIVE')
    obj, same_a, same_b = build_material_cube()
    total = len(obj.data.polygons)

    seed_a = min(same_a)
    enter_edit(obj, 'FACE')
    seed_face(obj, seed_a)
    run_op("select_same_material", selection_mode='REPLACE')
    got = edit_selected_faces(obj)
    check("立方体：同材质面（不相连）", got == same_a, f"期望 {sorted(same_a)} 实得 {sorted(got)}")
    exit_edit()
    check(
        "立方体：同材质面结果持久化到网格",
        object_selected_faces(obj) == same_a,
        f"对象模式 {sorted(object_selected_faces(obj))}",
    )
    summary = bpy.context.scene.paint_bucket.last_result
    check("立方体：最近结果写入场景属性", "测试立方体" in summary and "个面" in summary, summary)

    # 与内置相似选择对照
    enter_edit(obj, 'FACE')
    seed_face(obj, seed_a)
    bpy.ops.mesh.select_similar(type='FACE_MATERIAL', threshold=0.0)
    oracle_same = edit_selected_faces(obj)
    seed_face(obj, seed_a)
    run_op("select_same_material", selection_mode='REPLACE')
    ours_same = edit_selected_faces(obj)
    check("立方体：同材质结果与内置选择相似一致", ours_same == oracle_same,
          f"内置 {len(oracle_same)} / 插件 {len(ours_same)}")

    # 相连区域：两个红面互不相连 -> 只有种子面
    seed_face(obj, seed_a)
    run_op("select_connected", selection_mode='REPLACE')
    got_connected = edit_selected_faces(obj)
    check("立方体：相连区域只含种子面", got_connected == {seed_a}, f"实得 {sorted(got_connected)}")

    # 与内置 select_linked(delimit MATERIAL) 对照
    seed_face(obj, seed_a)
    bpy.ops.mesh.select_linked(delimit={'MATERIAL'})
    oracle_linked = edit_selected_faces(obj)
    check("立方体：相连结果与内置选择相连一致", oracle_linked == {seed_a},
          f"内置 {sorted(oracle_linked)}")

    # 绿面：4 个面围成一圈，相连结果应为 4
    seed_b = min(same_b)
    seed_face(obj, seed_b)
    run_op("select_connected", selection_mode='REPLACE')
    got_b = edit_selected_faces(obj)
    check("立方体：绿面相连区域为 4", got_b == same_b, f"期望 {sorted(same_b)} 实得 {sorted(got_b)}")

    # 相邻扩展：种子绿面 + 2 个绿邻居 = 3，红面不参与
    seed_face(obj, seed_b)
    run_op("select_adjacent", selection_mode='ADD')
    got_adjacent = edit_selected_faces(obj)
    expected_adjacent = {seed_b}
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    for edge in bm.faces[seed_b].edges:
        for face in edge.link_faces:
            if face.index != seed_b and face.material_index == 1:
                expected_adjacent.add(face.index)
    check(
        "立方体：相邻同材质加选",
        got_adjacent == expected_adjacent and len(expected_adjacent) == 3,
        f"期望 {sorted(expected_adjacent)} 实得 {sorted(got_adjacent)}",
    )

    # 反选同材质：红面 -> 其余 4 面
    seed_face(obj, seed_a)
    run_op("invert_material", selection_mode='REPLACE')
    got_invert = edit_selected_faces(obj)
    check("立方体：反选同材质", got_invert == same_b, f"期望 {sorted(same_b)} 实得 {sorted(got_invert)}")

    # 加选 / 减选
    seed_face(obj, seed_a)
    run_op("select_same_material", selection_mode='REPLACE')
    run_op("select_same_material", selection_mode='SUBTRACT')
    got_sub = edit_selected_faces(obj)
    check("立方体：减选同材质后清空", got_sub == set(), f"实得 {sorted(got_sub)}")

    run_op("select_same_material", selection_mode='ADD')
    got_add = edit_selected_faces(obj)
    check("立方体：加选同材质", got_add == same_a, f"期望 {sorted(same_a)} 实得 {sorted(got_add)}")

    check("立方体：面总数未被改变", len(obj.data.polygons) == total)
    exit_edit()


# --------------------------------------------------------------------------
# 3. UV 球：半球材质 + 面/边/点三种模式
# --------------------------------------------------------------------------
def build_material_sphere():
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=16, ring_count=8, radius=1.0, location=(0.0, 0.0, 0.0)
    )
    obj = bpy.context.object
    obj.name = "测试UV球"
    blue = make_material("上半蓝", (0.05, 0.2, 0.85))
    yellow = make_material("下半黄", (0.85, 0.7, 0.05))
    obj.data.materials.append(blue)
    obj.data.materials.append(yellow)
    for poly in obj.data.polygons:
        poly.material_index = 0 if poly.center.z > 0.05 else 1
    top = {poly.index for poly in obj.data.polygons if poly.material_index == 0}
    bottom = {poly.index for poly in obj.data.polygons if poly.material_index == 1}
    return obj, top, bottom


def test_sphere_modes():
    set_scene(match_mode='SLOT', tolerance=0.08, seed_source='ACTIVE')
    obj, top, bottom = build_material_sphere()
    total = len(obj.data.polygons)
    check("UV 球：多材质分组非空且覆盖全部", len(top) > 0 and len(bottom) > 0 and len(top) + len(bottom) == total,
          f"上 {len(top)} 下 {len(bottom)} 总 {total}")
    seed_top = max(top, key=lambda index: obj.data.polygons[index].center.z)

    # 面模式：全网格同材质
    enter_edit(obj, 'FACE')
    seed_face(obj, seed_top)
    run_op("select_same_material", selection_mode='REPLACE')
    got_faces = edit_selected_faces(obj)
    check("UV 球（面模式）：同材质面集合", got_faces == top, f"期望 {len(top)} 实得 {len(got_faces)}")

    # 相连区域应等于整个上半球
    seed_face(obj, seed_top)
    run_op("select_connected", selection_mode='REPLACE')
    got_connected = edit_selected_faces(obj)
    check("UV 球：相连区域等于上半球", got_connected == top,
          f"期望 {len(top)} 实得 {len(got_connected)}")

    # 内置 select_linked 对照
    seed_face(obj, seed_top)
    bpy.ops.mesh.select_linked(delimit={'MATERIAL'})
    oracle_linked = edit_selected_faces(obj)
    check("UV 球：相连结果与内置一致", oracle_linked == got_connected,
          f"内置 {len(oracle_linked)} 插件 {len(got_connected)}")
    exit_edit()

    # 顶点模式
    expected_verts = set()
    for index in top:
        expected_verts.update(obj.data.polygons[index].vertices)
    enter_edit(obj, 'VERT')
    seed_face(obj, seed_top)
    run_op("select_same_material", selection_mode='REPLACE')
    got_verts = edit_selected_verts(obj)
    check("UV 球（顶点模式）：选中顶点集合", got_verts == expected_verts,
          f"期望 {len(expected_verts)} 实得 {len(got_verts)}")
    exit_edit()
    check("UV 球（顶点模式）：结果持久化", object_selected_verts(obj) == expected_verts,
          f"对象模式 {len(object_selected_verts(obj))}")

    # 边模式
    edge_lookup = {tuple(sorted(edge.vertices)): edge.index for edge in obj.data.edges}
    expected_edges = set()
    for index in top:
        verts = list(obj.data.polygons[index].vertices)
        for i in range(len(verts)):
            key = tuple(sorted((verts[i], verts[(i + 1) % len(verts)])))
            expected_edges.add(edge_lookup[key])
    enter_edit(obj, 'EDGE')
    seed_face(obj, seed_top)
    run_op("select_same_material", selection_mode='REPLACE')
    got_edges = edit_selected_edges(obj)
    check("UV 球（边模式）：选中边集合", got_edges == expected_edges,
          f"期望 {len(expected_edges)} 实得 {len(got_edges)}")
    exit_edit()
    check("UV 球（边模式）：结果持久化", object_selected_edges(obj) == expected_edges,
          f"对象模式 {len(object_selected_edges(obj))}")
    check("UV 球：拓扑未被修改", len(obj.data.polygons) == total)


# --------------------------------------------------------------------------
# 4. 颜色匹配：同色不同槽 / 容差
# --------------------------------------------------------------------------
def build_color_cube():
    obj = make_cube("颜色立方体")
    red_a = make_material("红A", (0.8, 0.1, 0.1))
    red_b = make_material("红B同色", (0.8, 0.1, 0.1))
    orange = make_material("橙", (0.8, 0.35, 0.1))
    for mat in (red_a, red_b, orange):
        obj.data.materials.append(mat)

    red_faces = {face_by_normal(obj, 0, 1.0), face_by_normal(obj, 0, -1.0)}
    red_b_faces = {face_by_normal(obj, 1, 1.0), face_by_normal(obj, 1, -1.0)}
    orange_faces = {face_by_normal(obj, 2, 1.0), face_by_normal(obj, 2, -1.0)}
    for poly in obj.data.polygons:
        if poly.index in red_faces:
            poly.material_index = 0
        elif poly.index in red_b_faces:
            poly.material_index = 1
        else:
            poly.material_index = 2
    return obj, red_faces, red_b_faces, orange_faces


def test_color_matching():
    obj, red_faces, red_b_faces, orange_faces = build_color_cube()
    seed = min(red_faces)
    enter_edit(obj, 'FACE')

    set_scene(match_mode='SLOT', tolerance=0.01)
    seed_face(obj, seed)
    run_op("select_same_material", selection_mode='REPLACE')
    got_slot = edit_selected_faces(obj)
    check("颜色立方体：材质槽模式只选同槽", got_slot == red_faces,
          f"期望 {len(red_faces)} 实得 {len(got_slot)}")

    set_scene(match_mode='SLOT_OR_COLOR', tolerance=0.01)
    seed_face(obj, seed)
    run_op("select_same_material", selection_mode='REPLACE')
    got_or = edit_selected_faces(obj)
    check("颜色立方体：槽或颜色模式合并同色槽", got_or == red_faces | red_b_faces,
          f"期望 {len(red_faces | red_b_faces)} 实得 {len(got_or)}")

    seed_face(obj, seed)
    run_op("select_by_color", selection_mode='REPLACE', tolerance=0.01)
    got_color = edit_selected_faces(obj)
    check("颜色立方体：按颜色选中两个红面槽", got_color == red_faces | red_b_faces,
          f"实得 {len(got_color)}")

    seed_face(obj, seed)
    run_op("select_by_color", selection_mode='REPLACE', tolerance=0.3)
    got_color_wide = edit_selected_faces(obj)
    check("颜色立方体：容差 0.3 把橙色并入", got_color_wide == red_faces | red_b_faces | orange_faces,
          f"实得 {len(got_color_wide)}")

    set_scene(match_mode='SLOT', tolerance=0.08)
    seed_face(obj, seed)
    run_op("invert_material", selection_mode='REPLACE')
    got_invert = edit_selected_faces(obj)
    check("颜色立方体：反选同槽得其补集", got_invert == red_b_faces | orange_faces,
          f"实得 {len(got_invert)}")
    exit_edit()


# --------------------------------------------------------------------------
# 5. 无材质：面颜色回退 + 容差滑块
# --------------------------------------------------------------------------
def build_color_strip():
    verts = [(float(i), 0.0, 0.0) for i in range(5)] + [(float(i), 1.0, 0.0) for i in range(5)]
    faces = [(i, i + 1, i + 6, i + 5) for i in range(4)]
    mesh = bpy.data.meshes.new("色带网格")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("无材质色带", mesh)
    bpy.context.collection.objects.link(obj)

    colors = [
        (1.0, 0.0, 0.0, 1.0),
        (0.85, 0.0, 0.0, 1.0),
        (0.0, 0.0, 1.0, 1.0),
        (0.0, 0.0, 1.0, 1.0),
    ]
    attr = mesh.color_attributes.new(name="面颜色", type='FLOAT_COLOR', domain='CORNER')
    for poly in mesh.polygons:
        for loop_index in range(poly.loop_start, poly.loop_start + poly.loop_total):
            attr.data[loop_index].color = colors[poly.index]
    mesh.color_attributes.active_color = attr
    return obj


def test_face_color_fallback():
    obj = build_color_strip()
    check("色带：4 个面且无材质槽", len(obj.data.polygons) == 4 and len(obj.data.materials) == 0,
          f"面 {len(obj.data.polygons)} 材质 {len(obj.data.materials)}")

    enter_edit(obj, 'FACE')
    seed_face(obj, 0)
    set_scene(tolerance=0.05)
    run_op("select_by_color", selection_mode='REPLACE', tolerance=-1.0)
    got_narrow = edit_selected_faces(obj)
    check("无材质：容差 0.05 只选纯红面", got_narrow == {0}, f"实得 {sorted(got_narrow)}")

    seed_face(obj, 0)
    run_op("select_by_color", selection_mode='REPLACE', tolerance=0.2)
    got_wide = edit_selected_faces(obj)
    check("无材质：容差 0.2 并入暗红面", got_wide == {0, 1}, f"实得 {sorted(got_wide)}")

    seed_face(obj, 2)
    run_op("select_by_color", selection_mode='REPLACE', tolerance=0.05)
    got_blue = edit_selected_faces(obj)
    check("无材质：蓝色种子选中两个蓝面", got_blue == {2, 3}, f"实得 {sorted(got_blue)}")
    exit_edit()


# --------------------------------------------------------------------------
# 6. 非编辑模式与无种子
# --------------------------------------------------------------------------
def test_non_edit_mode():
    obj = make_cube("非编辑立方体")
    exit_edit()
    bpy.context.view_layer.objects.active = obj
    result = run_op("select_same_material", selection_mode='REPLACE')
    check("对象模式调用返回 CANCELLED", result == {'CANCELLED'}, f"返回 {result}")

    enter_edit(obj, 'FACE')
    bm = bmesh.from_edit_mesh(obj.data)
    clear_selection(bm)
    bm.faces.active = None
    bmesh.update_edit_mesh(obj.data, loop_triangles=False)
    result = run_op("select_same_material", selection_mode='REPLACE')
    check("编辑模式但无种子返回 CANCELLED", result == {'CANCELLED'}, f"返回 {result}")
    exit_edit()


def test_hover_fallback():
    """无头环境没有 3D 视图区域，悬停取面应安全回退到激活面。"""
    obj, same_a, _same_b = build_material_cube()
    set_scene(match_mode='SLOT', seed_source='HOVER')
    enter_edit(obj, 'FACE')
    seed_face(obj, min(same_a))
    result = run_op("select_same_material", selection_mode='REPLACE')
    got = edit_selected_faces(obj)
    check(
        "悬停模式无视图时回退激活面",
        result == {'FINISHED'} and got == same_a,
        f"返回 {result} 选中 {sorted(got)}",
    )
    exit_edit()
    set_scene(seed_source='ACTIVE')


class _FakeLayout:
    """记录面板绘制调用，用于无头验证 UI 结构与中文文案。"""

    def __init__(self, sink):
        self.sink = sink

    def __getattr__(self, name):
        def recorder(*args, **kwargs):
            self.sink.append((name, args, kwargs))
            return _FakeLayout(self.sink)

        return recorder


def test_panel_draw():
    panel_cls = getattr(bpy.types, "PAINTBUCKET_PT_main", None)
    if panel_cls is None:
        print("[INFO] 当前构建未在 bpy.types 暴露面板类，跳过绘制验证")
        return

    sink = []
    fake_self = types.SimpleNamespace(layout=_FakeLayout(sink))
    bpy.context.scene.paint_bucket.last_result = "（尚未使用）"
    panel_cls.draw(fake_self, bpy.context)

    buttons = [
        kwargs.get("text")
        for name, args, kwargs in sink
        if name == "operator" and args
    ]
    expected = [
        "选择同材质面",
        "选择相连同材质区",
        "加选",
        "减选",
        "按颜色相近选择",
        "加选相邻同材质面",
        "反选同材质",
    ]
    check("面板绘制出 7 个按钮", buttons == expected, str(buttons))
    check(
        "按钮文案全为中文",
        all(any("\u4e00" <= ch <= "\u9fff" for ch in text) for text in buttons if text),
        str(buttons),
    )
    labels = [kwargs.get("text", "") for name, args, kwargs in sink if name == "label"]
    check(
        "非编辑模式给出中文提示",
        any("编辑模式" in text for text in labels),
        str([text for text in labels if text]),
    )
    check(
        "面板展示最近结果",
        any("最近结果" in text for text in labels),
        str(labels),
    )


def test_multi_object():
    """多对象同时进入编辑模式时，每个对象各自用激活面作种子。"""
    reset_file()
    set_scene(match_mode='SLOT', tolerance=0.08, seed_source='ACTIVE')

    first = make_cube(name="立方体A")
    red = make_material("红漆", (0.8, 0.05, 0.05))
    green = make_material("绿漆", (0.05, 0.7, 0.1))
    for obj in (first,):
        obj.data.materials.append(red)
        obj.data.materials.append(green)
    same_first = {face_by_normal(first, 0, 1.0), face_by_normal(first, 0, -1.0)}
    for poly in first.data.polygons:
        poly.material_index = 0 if poly.index in same_first else 1

    second = make_cube(name="立方体B")
    second.location = (3.0, 0.0, 0.0)
    second.data.materials.append(red)
    second.data.materials.append(green)
    same_second = {face_by_normal(second, 0, 1.0), face_by_normal(second, 0, -1.0)}
    for poly in second.data.polygons:
        poly.material_index = 0 if poly.index in same_second else 1

    bpy.ops.object.mode_set(mode='OBJECT')
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    first.select_set(True)
    second.select_set(True)
    bpy.context.view_layer.objects.active = first
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.context.tool_settings.mesh_select_mode = (False, False, True)

    seed_face(first, min(same_first))
    seed_face(second, min(same_second))
    result = run_op("select_same_material", selection_mode='REPLACE')
    got_first = edit_selected_faces(first)
    got_second = edit_selected_faces(second)
    check(
        "多对象：两个对象各自选中同材质面",
        result == {'FINISHED'} and got_first == same_first and got_second == same_second,
        f"A {sorted(got_first)} / B {sorted(got_second)}",
    )
    check(
        "多对象：汇总包含两个对象",
        "立方体A" in bpy.context.scene.paint_bucket.last_result
        and "立方体B" in bpy.context.scene.paint_bucket.last_result,
        bpy.context.scene.paint_bucket.last_result,
    )
    exit_edit()


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
def main():
    reset_file()
    addon.register()
    try:
        test_registration()
        test_panel_draw()
        test_material_cube()
        test_multi_object()
        test_sphere_modes()
        test_color_matching()
        test_face_color_fallback()
        test_non_edit_mode()
        test_hover_fallback()
    finally:
        addon.unregister()

    failed = [item for item in RESULTS if not item[1]]
    print("\n===== 汇总 =====")
    print(f"用例总数: {len(RESULTS)}  通过: {len(RESULTS) - len(failed)}  失败: {len(failed)}")
    for name, _ok, detail in failed:
        print(f"  失败: {name} | {detail}")
    print("===== 结论:", "全部通过" if not failed else "存在失败", "=====")
    if failed:
        sys.exit(1)


main()
