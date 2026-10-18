bl_info = {
    "name": "GTA Minimap Maker",
    "author": "Bigbigdog",
    "version": (1, 3),
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar > GTA Tools",
    "description": "Create GTA V minimaps using Sollumz 2.9.0.",
    "warning": "",
    "wiki_url": "https://github.com/Vakhrush/GTA-Minimap-Maker/",
    "category": "3D View",
}

import bpy

from bpy.props import StringProperty, BoolProperty
from . import operator, panel, preferences


modules = (operator, panel, preferences)


def register():
    bpy.types.Scene.mlo_name = StringProperty(
        name="MLO Name",
        default=""
    )

    bpy.types.Scene.has_basement = BoolProperty(
        name="Has basement",
        default=False
    )

    for mod in modules:
        if hasattr(mod, "classes"):
            for cls in mod.classes:
                bpy.utils.register_class(cls)

    addon_entry = bpy.context.preferences.addons.get(__package__)
    if addon_entry is not None:
        preferences.migrate_preferences(addon_entry.preferences)


def unregister():

    del bpy.types.Scene.has_basement
    del bpy.types.Scene.mlo_name

    for mod in reversed(modules):
        if hasattr(mod, "classes"):
            for cls in reversed(mod.classes):
                bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
