# -*- coding: utf-8 -*-
"""3D 视图侧栏面板：油漆桶选择的中文界面。"""

import bpy


class PAINTBUCKET_PT_main(bpy.types.Panel):
    """侧栏主面板，集中放置所有油漆桶按钮。"""

    bl_label = "油漆桶选择"
    bl_idname = "PAINTBUCKET_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "油漆桶"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = getattr(context.scene, "paint_bucket", None)
        if settings is None:
            layout.label(text="属性组未注册，请重新启用插件", icon='ERROR')
            return

        # 模式提示：非编辑模式只提示，不隐藏按钮，点击后由操作符给出状态栏信息
        if context.mode != 'EDIT_MESH':
            box = layout.box()
            box.label(text="当前不在编辑模式", icon='INFO')
            box.label(text="按 Tab 进入编辑模式后使用")
        elif context.edit_object is None or context.edit_object.type != 'MESH':
            box = layout.box()
            box.label(text="请选择一个网格对象", icon='INFO')

        column = layout.column(align=True)
        column.prop(settings, "seed_source", text="种子来源")
        column.prop(settings, "match_mode", text="匹配依据")

        tolerance_row = layout.row(align=True)
        tolerance_row.prop(settings, "tolerance", text="颜色容差", slider=True)

        layout.separator()
        primary = layout.column(align=True)
        primary.operator(
            "paint_bucket.select_same_material",
            text="选择同材质面",
            icon='MATERIAL',
        )
        primary.operator(
            "paint_bucket.select_connected",
            text="选择相连同材质区",
            icon='LINKED',
        )

        extend_row = layout.row(align=True)
        extend_row.operator(
            "paint_bucket.select_same_material",
            text="加选",
            icon='ADD',
        ).selection_mode = 'ADD'
        extend_row.operator(
            "paint_bucket.select_same_material",
            text="减选",
            icon='REMOVE',
        ).selection_mode = 'SUBTRACT'

        layout.separator()
        color_box = layout.box()
        color_box.label(text="按颜色选择（无材质时用面颜色）", icon='COLOR')
        color_box.operator(
            "paint_bucket.select_by_color",
            text="按颜色相近选择",
            icon='COLOR',
        )

        layout.separator()
        advanced = layout.column(align=True)
        advanced.operator(
            "paint_bucket.select_adjacent",
            text="加选相邻同材质面",
            icon='SELECT_EXTEND',
        )
        advanced.operator(
            "paint_bucket.invert_material",
            text="反选同材质",
            icon='SELECT_DIFFERENCE',
        )

        layout.separator()
        result_box = layout.box()
        result_box.label(text="最近结果", icon='INFO')
        result_box.label(text=settings.last_result)


classes = (PAINTBUCKET_PT_main,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
