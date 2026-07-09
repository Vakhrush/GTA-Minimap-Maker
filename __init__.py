bl_info = {
    "name": "GTA Minimap Maker",
    "author": "Bigbigdog",
    "version": (1, 1),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > GTA Tools",
    "description": "Create GTA minimap from Sollumz scenes",
    "warning": "",
    "wiki_url": "https://github.com/Vakhrush/GTA-Minimap-Maker/",
    "category": "3D View",
}

import bpy

from bpy.props import StringProperty, EnumProperty, BoolProperty
from . import operator, panel, preferences


modules = (operator, panel, preferences)


def register():
    bpy.types.Scene.mlo_name = StringProperty(
        name="MLO Name",
        default=""
    )

    bpy.types.Scene.minimap_floors = EnumProperty(
        items=[
            ('1', "1", ""),
            ('2', "2", ""),
            ('3', "3", ""),
            ('4', "4", ""),
        ],
        default='1'
    )

    bpy.types.Scene.has_basement = BoolProperty(
        name="Has basement",
        default=False
    )

    for mod in modules:
        if hasattr(mod, "classes"):
            for cls in mod.classes:
                bpy.utils.register_class(cls)


def unregister():

    del bpy.types.Scene.minimap_floors
    del bpy.types.Scene.has_basement
    del bpy.types.Scene.mlo_name

    for mod in reversed(modules):
        if hasattr(mod, "classes"):
            for cls in reversed(mod.classes):
                bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
