# -*- coding: utf-8 -*-
"""油漆桶选择：按材质或颜色一键选中整块面的 Blender 扩展。"""

from . import operators, panel, properties

__all__ = ("register", "unregister")


def register():
    """按依赖顺序注册属性组、操作符与侧栏面板。"""
    properties.register()
    operators.register()
    panel.register()


def unregister():
    """按注册的逆序注销，重复调用不会抛异常。"""
    panel.unregister()
    operators.unregister()
    properties.unregister()
