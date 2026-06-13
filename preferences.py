import bpy


class GTAMINIMAP_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    output_path: bpy.props.StringProperty(
        name="Output Path",
        description="Directory to save minimap shots",
        subtype='DIR_PATH',
        default=""
    )

    shot_resolution: bpy.props.IntProperty(
        name="Shot Resolution",
        description="Resolution for the minimap shot (pixels)",
        default=2048,
        min=1024,
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
        layout.prop(self, "shot_resolution")
        layout.separator()
        box = layout.box()
        box.label(text="Minimap Colors")
        box.prop(self, 'entity_color')
        box.prop(self, 'shell_color')
        box.prop(self, 'background_color')

        layout.separator()
        cbox = layout.box()
        cbox.label(text="Custom Paint")
        cbox.prop(self, 'custom_paint_color')


classes = (GTAMINIMAP_Preferences,)
