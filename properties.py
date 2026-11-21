# -*- coding: utf-8 -*-
"""场景级属性组：保存油漆桶选择的参数与最近一次操作结果。"""

import bpy
from bpy.props import EnumProperty, FloatProperty, PointerProperty, StringProperty


class PAINTBUCKET_PG_settings(bpy.types.PropertyGroup):
    """挂在 Scene 上的参数集合，随 .blend 文件保存。"""

    seed_source: EnumProperty(
        name="种子来源",
        description="油漆桶从哪个面开始扩散",
        items=(
            ('ACTIVE', "激活面", "使用激活面（最后一次点选的面）作为种子"),
            ('HOVER', "鼠标悬停面", "使用鼠标指针下的面；取不到时自动回退到激活面"),
        ),
        default='ACTIVE',
    )

    match_mode: EnumProperty(
        name="匹配依据",
        description="判断两个面是否属于同一色块的方式",
        items=(
            ('SLOT', "材质槽", "材质槽索引相同，或两个面指向同一个材质"),
            ('SLOT_OR_COLOR', "槽或颜色", "材质槽相同，或材质颜色在容差内一致"),
            ('COLOR', "仅颜色", "只比较颜色，材质槽不同也能选中"),
        ),
        default='SLOT_OR_COLOR',
    )

    tolerance: FloatProperty(
        name="颜色容差",
        description="RGB 单通道允许的最大差值，0 表示颜色必须完全一致",
        default=0.08,
        min=0.0,
        max=1.0,
        step=1,
        precision=3,
        subtype='FACTOR',
    )

    last_result: StringProperty(
        name="最近结果",
        description="上一次油漆桶选择的结果摘要",
        default="就绪",
        options={'SKIP_SAVE'},
    )


classes = (PAINTBUCKET_PG_settings,)


def register():
    """注册属性组并挂到 Scene 上。"""
    for cls in classes:
        bpy.utils.register_class(cls)
    # 重载插件时先清掉旧指针，避免指向已注销的 RNA 类型
    if hasattr(bpy.types.Scene, "paint_bucket"):
        del bpy.types.Scene.paint_bucket
    bpy.types.Scene.paint_bucket = PointerProperty(
        type=PAINTBUCKET_PG_settings,
        name="油漆桶选择设置",
        description="油漆桶选择的全部参数",
    )


def unregister():
    """注销 Scene 属性与属性组类。"""
    if hasattr(bpy.types.Scene, "paint_bucket"):
        del bpy.types.Scene.paint_bucket
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
