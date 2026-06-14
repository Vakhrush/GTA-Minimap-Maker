bl_info = {
    "name": "GTA Minimap Maker",
    "author": "Bigbigdog",
    "version": (0, 1),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > GTA Tools",
    "description": "Tools to prepare and render minimap shots for GTA-style maps",
    "warning": "",
    "wiki_url": "",
    "category": "3D View",
}

import bpy

from bpy.props import StringProperty
from . import operator, panel, preferences


modules = (operator, panel, preferences)


def register():
    bpy.types.Scene.mlo_name = StringProperty(
        name="MLO Name",
        default=""
    )

    for mod in modules:
        if hasattr(mod, "classes"):
            for cls in mod.classes:
                bpy.utils.register_class(cls)


def unregister():

    del bpy.types.Scene.mlo_name

    for mod in reversed(modules):
        if hasattr(mod, "classes"):
            for cls in reversed(mod.classes):
                bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
