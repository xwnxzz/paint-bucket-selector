# -*- coding: utf-8 -*-
"""油漆桶选择操作符：用 bmesh 在编辑模式下按材质或颜色扩散选面。

设计要点：
- 一律在 bmesh 上读写选择标记，最后一次性写回编辑网格，避免依赖上下文操作符；
- 面/边/顶点三种选择模式都可用，选中面后同步选中其边与顶点；
- 关联区域用共享边做洪水填充，互不相连的同材质面用全网格匹配；
- 颜色比较使用材质视图颜色（diffuse_color），无材质时回退到面颜色属性。
"""

import bmesh
import bpy
from bpy.props import EnumProperty, FloatProperty
from bpy_extras import view3d_utils

# 选择方式：替换 / 加选 / 减选
SELECTION_MODE_ITEMS = (
    ('REPLACE', "替换", "先清空选择，再选中匹配的面"),
    ('ADD', "加选", "保留已有选择，追加匹配的面"),
    ('SUBTRACT', "减选", "从已有选择中移除匹配的面"),
)


# --------------------------------------------------------------------------
# 基础读取
# --------------------------------------------------------------------------
def _settings(context):
    """取场景上的油漆桶属性组；属性未注册时返回 None。"""
    return getattr(context.scene, "paint_bucket", None)


def _edit_objects(context):
    """返回当前编辑模式下的所有网格对象。"""
    objs = [obj for obj in context.objects_in_mode if obj.type == 'MESH']
    if not objs:
        obj = context.edit_object
        if obj is not None and obj.type == 'MESH':
            objs = [obj]
    return objs


def _slot_material(obj, material_index):
    """按材质槽索引取材质，越界或无槽时返回 None。"""
    slots = obj.material_slots
    if 0 <= material_index < len(slots):
        return slots[material_index].material
    return None


def _material_color(material):
    """材质视图颜色，用于“同材质颜色”的比较。"""
    if material is None:
        return None
    color = material.diffuse_color
    return (float(color[0]), float(color[1]), float(color[2]))


def _average(cols):
    """对一组 RGB 求平均，忽略 alpha。"""
    if not cols:
        return None
    total = [0.0, 0.0, 0.0]
    for col in cols:
        total[0] += float(col[0])
        total[1] += float(col[1])
        total[2] += float(col[2])
    count = float(len(cols))
    return (total[0] / count, total[1] / count, total[2] / count)


def _loop_color(loop, layer):
    """读取 bmesh 颜色层上的单个环颜色，兼容浮点层与字节层。"""
    value = loop[layer]
    color = getattr(value, "color", value)
    return (float(color[0]), float(color[1]), float(color[2]))


def _face_color_bm(bm, face):
    """从 bmesh 的颜色层取面颜色，取不到时返回 None。"""
    layer = bm.loops.layers.float_color.active
    if layer is not None:
        try:
            return _average([_loop_color(loop, layer) for loop in face.loops])
        except (TypeError, ValueError, IndexError):
            pass
    layer = bm.loops.layers.color.active
    if layer is not None:
        try:
            return _average([_loop_color(loop, layer) for loop in face.loops])
        except (TypeError, ValueError, IndexError):
            pass
    vertex_layer = bm.verts.layers.float_color.active
    if vertex_layer is not None:
        try:
            return _average(
                [
                    (
                        float(vert[vertex_layer][0]),
                        float(vert[vertex_layer][1]),
                        float(vert[vertex_layer][2]),
                    )
                    for vert in face.verts
                ]
            )
        except (TypeError, ValueError, IndexError):
            pass
    return None


def _face_color_mesh(mesh, face_index):
    """面颜色回退：直接读网格的颜色属性（角点域或点域）。"""
    attr = mesh.color_attributes.active_color
    if attr is None and len(mesh.color_attributes) > 0:
        attr = mesh.color_attributes[0]
    if attr is None:
        return None
    poly = mesh.polygons[face_index]
    data = attr.data
    cols = []
    try:
        if attr.domain == 'CORNER':
            indices = range(poly.loop_start, poly.loop_start + poly.loop_total)
        else:
            indices = poly.vertices
        for index in indices:
            color = data[index].color
            cols.append((float(color[0]), float(color[1]), float(color[2])))
    except (IndexError, AttributeError, TypeError):
        return None
    return _average(cols)


def _face_color(obj, bm, face):
    """面颜色：有材质用材质视图颜色，无材质用面颜色属性。"""
    material = _slot_material(obj, face.material_index)
    if material is not None:
        return _material_color(material)
    color = _face_color_bm(bm, face)
    if color is not None:
        return color
    return _face_color_mesh(obj.data, face.index)


def _color_close(color_a, color_b, tolerance):
    """RGB 三通道最大差值不超过容差即视为同色。"""
    if color_a is None or color_b is None:
        return False
    return max(abs(color_a[i] - color_b[i]) for i in range(3)) <= tolerance + 1e-9


# --------------------------------------------------------------------------
# 匹配器
# --------------------------------------------------------------------------
def _make_matcher(obj, bm, seed_face, mode, tolerance):
    """构造按面判断的函数，返回 (匹配函数, 种子颜色, 种子材质槽)。

    mode 为 COLOR 且种子面没有任何颜色信息时返回 None。
    """
    seed_index = seed_face.material_index
    seed_material = _slot_material(obj, seed_index)
    seed_color = _face_color(obj, bm, seed_face)
    color_cache = {}

    def face_color(face):
        cached = color_cache.get(face.index)
        if cached is not None:
            return cached
        color = _face_color(obj, bm, face)
        color_cache[face.index] = color
        return color

    def same_slot(face):
        if face.material_index == seed_index:
            return True
        if seed_material is None:
            return False
        return _slot_material(obj, face.material_index) is seed_material

    def same_color(face):
        return _color_close(face_color(face), seed_color, tolerance)

    if mode == 'COLOR':
        if seed_color is None:
            return None
        return same_color, seed_color, seed_index
    if mode == 'SLOT':
        return same_slot, seed_color, seed_index

    def slot_or_color(face):
        return same_slot(face) or same_color(face)

    return slot_or_color, seed_color, seed_index


def _flood_connected(bm, seed_face, matcher):
    """沿共享边洪水填充，只穿过匹配的面。"""
    if not matcher(seed_face):
        return {seed_face}
    visited = {seed_face}
    stack = [seed_face]
    while stack:
        face = stack.pop()
        for edge in face.edges:
            for neighbor in edge.link_faces:
                if neighbor in visited:
                    continue
                if matcher(neighbor):
                    visited.add(neighbor)
                    stack.append(neighbor)
    return visited


def _adjacent_faces(bm, seeds, matcher):
    """返回与 seeds 相邻（共享边）且匹配的面，不含 seeds 自身。"""
    result = set()
    for face in seeds:
        for edge in face.edges:
            for neighbor in edge.link_faces:
                if neighbor not in seeds and matcher(neighbor):
                    result.add(neighbor)
    return result


# --------------------------------------------------------------------------
# 选择写回
# --------------------------------------------------------------------------
def _apply_selection(bm, targets, selection_mode):
    """把目标面集合写入 bmesh 选择标记，并同步边与顶点。"""
    if selection_mode == 'REPLACE':
        for face in bm.faces:
            face.select = False
        for edge in bm.edges:
            edge.select = False
        for vert in bm.verts:
            vert.select = False

    if selection_mode == 'SUBTRACT':
        for face in targets:
            face.select = False
        # 由剩余选中面反推边与顶点，避免留下孤立选中的顶点
        for edge in bm.edges:
            edge.select = any(face.select for face in edge.link_faces)
        for vert in bm.verts:
            vert.select = any(edge.select for edge in vert.link_edges)
        return

    for face in targets:
        face.select = True
        for edge in face.edges:
            edge.select = True
        for vert in face.verts:
            vert.select = True


# --------------------------------------------------------------------------
# 种子与悬停
# --------------------------------------------------------------------------
def _active_face_index(bm):
    """优先激活面，其次最后一个选中面；都没有时返回 None。"""
    face = bm.faces.active
    if face is not None and face.is_valid:
        return face.index, "激活面"
    selected = [item for item in bm.faces if item.select]
    if selected:
        return max(selected, key=lambda item: item.index).index, "已选面"
    return None, ""


def _hover_hit(context, mouse):
    """把 3D 视图鼠标坐标射线投射到场景，返回 (对象, 面索引) 或 None。"""
    if mouse is None:
        return None
    region = context.region
    region_data = context.region_data
    if region is None or region_data is None or region.type != 'WINDOW':
        return None
    if view3d_utils is None:
        return None
    try:
        coord = (float(mouse[0]), float(mouse[1]))
        origin = view3d_utils.region_2d_to_origin_3d(region, region_data, coord)
        direction = view3d_utils.region_2d_to_vector_3d(region, region_data, coord)
        depsgraph = context.evaluated_depsgraph_get()
        hit, _location, _normal, index, hit_object, _matrix = context.scene.ray_cast(
            depsgraph, origin, direction
        )
    except (RuntimeError, TypeError, ValueError):
        return None
    if not hit or hit_object is None:
        return None
    original = getattr(hit_object, "original", hit_object)
    return original, int(index)


# --------------------------------------------------------------------------
# 核心执行
# --------------------------------------------------------------------------
# 动作：同材质 / 相连区域 / 相邻扩展 / 反选 / 按颜色
ACTION_SAME = 'SAME'
ACTION_CONNECTED = 'CONNECTED'
ACTION_ADJACENT = 'ADJACENT'
ACTION_INVERT = 'INVERT'
ACTION_COLOR = 'COLOR'


def _execute_selection(operator, context, action, selection_mode, tolerance_override=None):
    """所有操作符共用的执行入口，返回 Blender 操作符结果集合。"""
    if context.mode != 'EDIT_MESH':
        operator.report({'WARNING'}, "请先进入编辑模式（Tab）后再使用油漆桶选择")
        return {'CANCELLED'}

    objects = _edit_objects(context)
    if not objects:
        operator.report({'WARNING'}, "当前没有可编辑的网格对象")
        return {'CANCELLED'}

    settings = _settings(context)
    if settings is not None:
        seed_source = settings.seed_source
        match_mode = settings.match_mode
        tolerance = settings.tolerance
    else:
        seed_source = 'ACTIVE'
        match_mode = 'SLOT_OR_COLOR'
        tolerance = 0.08

    if tolerance_override is not None and tolerance_override >= 0.0:
        tolerance = tolerance_override

    hover = _hover_hit(context, getattr(operator, "_mouse", None)) if seed_source == 'HOVER' else None
    hover_used = False

    total_selected = 0
    total_matched = 0
    object_reports = []

    for obj in objects:
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        if not bm.faces:
            continue

        seed_index = None
        seed_label = ""
        if hover is not None and hover[0] is obj and 0 <= hover[1] < len(bm.faces):
            seed_index = hover[1]
            seed_label = "悬停面"
            hover_used = True
        else:
            seed_index, seed_label = _active_face_index(bm)
        if seed_index is None or seed_index >= len(bm.faces):
            object_reports.append(f"{obj.name}：没有种子面")
            continue

        seed_face = bm.faces[seed_index]
        mode = 'COLOR' if action == ACTION_COLOR else match_mode
        matcher = _make_matcher(obj, bm, seed_face, mode, tolerance)
        if matcher is None:
            object_reports.append(f"{obj.name}：种子面缺少颜色信息")
            continue
        match_func, seed_color, _seed_slot = matcher

        if action == ACTION_SAME:
            targets = {face for face in bm.faces if match_func(face)}
        elif action == ACTION_CONNECTED:
            targets = _flood_connected(bm, seed_face, match_func)
        elif action == ACTION_ADJACENT:
            current = {face for face in bm.faces if face.select}
            if not current:
                current = {seed_face}
            targets = _adjacent_faces(bm, current, match_func)
        elif action == ACTION_INVERT:
            targets = {face for face in bm.faces if not match_func(face)}
        else:  # ACTION_COLOR
            targets = {face for face in bm.faces if match_func(face)}

        if not targets:
            object_reports.append(f"{obj.name}：没有匹配的面")
            continue

        _apply_selection(bm, targets, selection_mode)
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        selected_count = len([face for face in bm.faces if face.select])
        total_selected += selected_count
        total_matched += len(targets)

        material = _slot_material(obj, seed_face.material_index)
        material_name = material.name if material is not None else "无材质"
        object_reports.append(
            f"{obj.name}：{seed_label} 匹配 {len(targets)} 个面，"
            f"当前选中 {selected_count} 个（{material_name}）"
        )

    summary = "；".join(object_reports) if object_reports else "没有可处理的面"
    if settings is not None:
        settings.last_result = summary

    if total_matched == 0:
        operator.report({'WARNING'}, f"油漆桶选择：{summary}")
        return {'CANCELLED'}

    if seed_source == 'HOVER' and not hover_used:
        operator.report({'INFO'}, "未取到鼠标悬停面，已回退到激活面")
    if selection_mode == 'SUBTRACT':
        operator.report({'INFO'}, f"已减选 {total_matched} 个面，剩余选中 {total_selected} 个")
    else:
        operator.report({'INFO'}, f"已选择 {total_selected} 个面")
    return {'FINISHED'}


# --------------------------------------------------------------------------
# 操作符
# --------------------------------------------------------------------------
class PaintBucketMixin:
    """公共 invoke：记录鼠标位置，供悬停取面使用。"""

    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        try:
            self._mouse = (event.mouse_region_x, event.mouse_region_y)
        except AttributeError:
            self._mouse = None
        return self.execute(context)


class PAINTBUCKET_OT_select_same_material(PaintBucketMixin, bpy.types.Operator):
    bl_idname = "paint_bucket.select_same_material"
    bl_label = "选择同材质面"
    bl_description = "选中整个网格中与种子面材质相同的所有面（互不相连也会选中）"

    selection_mode: EnumProperty(
        name="选择方式",
        description="如何处理已有选择",
        items=SELECTION_MODE_ITEMS,
        default='REPLACE',
    )

    def execute(self, context):
        return _execute_selection(self, context, ACTION_SAME, self.selection_mode)


class PAINTBUCKET_OT_select_connected(PaintBucketMixin, bpy.types.Operator):
    bl_idname = "paint_bucket.select_connected"
    bl_label = "选择相连同材质区"
    bl_description = "从种子面沿共享边扩散，只选中连成一片的同材质面"

    selection_mode: EnumProperty(
        name="选择方式",
        description="如何处理已有选择",
        items=SELECTION_MODE_ITEMS,
        default='REPLACE',
    )

    def execute(self, context):
        return _execute_selection(self, context, ACTION_CONNECTED, self.selection_mode)


class PAINTBUCKET_OT_select_adjacent(PaintBucketMixin, bpy.types.Operator):
    bl_idname = "paint_bucket.select_adjacent"
    bl_label = "相邻同材质面"
    bl_description = "把当前选择向外扩展一圈：加选共享边且材质相同的面"

    selection_mode: EnumProperty(
        name="选择方式",
        description="如何处理已有选择",
        items=SELECTION_MODE_ITEMS,
        default='ADD',
    )

    def execute(self, context):
        return _execute_selection(self, context, ACTION_ADJACENT, self.selection_mode)


class PAINTBUCKET_OT_invert_material(PaintBucketMixin, bpy.types.Operator):
    bl_idname = "paint_bucket.invert_material"
    bl_label = "反选同材质"
    bl_description = "选中网格中所有与种子面材质不同的面"

    selection_mode: EnumProperty(
        name="选择方式",
        description="如何处理已有选择",
        items=SELECTION_MODE_ITEMS,
        default='REPLACE',
    )

    def execute(self, context):
        return _execute_selection(self, context, ACTION_INVERT, self.selection_mode)


class PAINTBUCKET_OT_select_by_color(PaintBucketMixin, bpy.types.Operator):
    bl_idname = "paint_bucket.select_by_color"
    bl_label = "按颜色相近选择"
    bl_description = "按颜色容差选中与种子面颜色相近的所有面，无材质时回退到面颜色"

    tolerance: FloatProperty(
        name="容差",
        description="覆盖侧栏的颜色容差；小于 0 时使用侧栏设置",
        default=-1.0,
        min=-1.0,
        max=1.0,
        precision=3,
    )
    selection_mode: EnumProperty(
        name="选择方式",
        description="如何处理已有选择",
        items=SELECTION_MODE_ITEMS,
        default='REPLACE',
    )

    def execute(self, context):
        return _execute_selection(
            self, context, ACTION_COLOR, self.selection_mode, self.tolerance
        )


classes = (
    PAINTBUCKET_OT_select_same_material,
    PAINTBUCKET_OT_select_connected,
    PAINTBUCKET_OT_select_adjacent,
    PAINTBUCKET_OT_invert_material,
    PAINTBUCKET_OT_select_by_color,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
