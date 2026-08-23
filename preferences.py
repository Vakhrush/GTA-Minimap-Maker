import bpy


def update_shot_quality(self, context):
    quality_map = {
        'LOW': 1024,
        'MEDIUM': 2048,
        'HIGH': 4096,
        'ULTRA': 8192,
    }
    self.shot_resolution = quality_map.get(self.shot_quality, 2048)


class GTAMINIMAP_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    output_path: bpy.props.StringProperty(
        name="Output Path",
        description="Directory to save minimap shots",
        subtype='DIR_PATH',
        default=""
    )

    jpexs_path: bpy.props.StringProperty(
        name="JPEXS Folder",
        description="Folder containing ffdec.bat",
        subtype='DIR_PATH',
        default=""
    )

    shot_resolution: bpy.props.IntProperty(
        name="Shot Resolution",
        description="Resolution for the minimap shot (pixels)",
        default=2048,
        min=1024,
    )

    shot_quality: bpy.props.EnumProperty(
        name="Shot Quality",
        description="Quick selector for shot resolution",
        items=(
            ('LOW', "Low", "", 0),
            ('MEDIUM', "Medium", "", 1),
            ('HIGH', "High", "", 2),
            ('ULTRA', "Ultra", "", 3),
        ),
        default='MEDIUM',
        update=update_shot_quality,
    )

    author: bpy.props.StringProperty(
        name="Author",
        description="Author name written into exported XML",
        default=""
    )

    entity_color: bpy.props.FloatVectorProperty(
        name="Entity Color",
        description="Color for entities",
        subtype='COLOR',
        size=4,
        min=0.0,
        max=1.0,
        # default: #6f6f6fff
        default=(0.158961, 0.158961, 0.158961, 1.0)
    )

    shell_color: bpy.props.FloatVectorProperty(
        name="Shell Color",
        description="Color for shell objects",
        subtype='COLOR',
        size=4,
        min=0.0,
        max=1.0,
        # default: #949494ff
        default=(0.302126, 0.302126, 0.302126, 1.0)
    )

    background_color: bpy.props.FloatVectorProperty(
        name="Background Color",
        description="Color for viewport background",
        subtype='COLOR',
        size=4,
        min=0.0,
        max=1.0,
        # default: #424242ff
        default=(0.051269, 0.051269, 0.051269, 1.0)
    )

    show_background: bpy.props.BoolProperty(
        name="Background",
        description="Include the background layer in the final merged SVG",
        default=True
    )

    auto_walls_from_shell: bpy.props.BoolProperty(
        name="Automatically create walls from shell",
        description="Add an offset of the shell contour to the walls layer",
        default=False
    )

    wall_thickness: bpy.props.FloatProperty(
        name="Wall Thickness",
        description="Outward shell offset in Blender units",
        default=0.001,
        min=0.0
    )

    custom_paint_color: bpy.props.FloatVectorProperty(
        name="Custom Paint Color",
        description="Color applied to selected meshes",
        subtype='COLOR',
        size=4,
        min=0.0,
        max=1.0,
        default=(1.0, 1.0, 1.0, 1.0)
    )


    def draw(self, context):
        layout = self.layout
        layout.label(text="GTA Minimap Maker Preferences")
        layout.prop(self, "output_path")
        layout.prop(self, "jpexs_path")
        layout.prop(self, "shot_resolution")
        layout.prop(self, "author")
        layout.separator()
        box = layout.box()
        box.label(text="Minimap Colors")
        box.prop(self, 'entity_color')
        box.prop(self, 'shell_color')
        box.prop(self, 'background_color', text="Walls")

        layout.prop(self, 'show_background')

        layout.separator()
        cbox = layout.box()
        cbox.label(text="Custom Paint")
        cbox.prop(self, 'custom_paint_color')


classes = (GTAMINIMAP_Preferences,)
