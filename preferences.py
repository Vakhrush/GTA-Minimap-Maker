import bpy

QUALITY_RESOLUTIONS = {'LOW': 1024, 'MEDIUM': 2048, 'HIGH': 4096, 'ULTRA': 8192}


def migrate_preferences(prefs):
    if prefs is None or getattr(prefs, 'settings_version', 0) >= 2:
        return
    if not prefs.is_property_set('manual_quality'):
        prefs.manual_quality = prefs.shot_resolution != QUALITY_RESOLUTIONS.get(prefs.shot_quality, 2048)
    legacy = prefs.is_property_set('show_background') or prefs.is_property_set('auto_walls_from_shell')
    if not prefs.is_property_set('background_enabled') and legacy:
        prefs.background_enabled = prefs.show_background or prefs.auto_walls_from_shell
    if not prefs.is_property_set('background_mode'):
        prefs.background_mode = ('FILL' if legacy and prefs.show_background
                                 and not prefs.auto_walls_from_shell else 'SHELL')
    prefs.settings_version = 2


def background_options(prefs):
    """Return (fill, shell walls), never enabling both."""
    if prefs is None:
        return False, True
    migrate_preferences(prefs)
    if not prefs.background_enabled:
        return False, False
    return prefs.background_mode == 'FILL', prefs.background_mode == 'SHELL'


def map_resolution(prefs):
    if prefs is None:
        return 2048
    migrate_preferences(prefs)
    return max(1024, int(prefs.shot_resolution if prefs.manual_quality else
                         QUALITY_RESOLUTIONS.get(prefs.shot_quality, 2048)))


def update_shot_quality(self, context):
    if not self.manual_quality:
        self.shot_resolution = QUALITY_RESOLUTIONS.get(self.shot_quality, 2048)


class GTAMINIMAP_OT_choose_background(bpy.types.Operator):
    bl_idname = 'gtaminimap.choose_background'
    bl_label = 'Choose Background Mode'
    mode: bpy.props.EnumProperty(items=[('FILL', 'Fill Background', ''), ('SHELL', 'Automatically Create Walls from Shell', '')])

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        prefs.background_mode = self.mode
        return {'FINISHED'}


class GTAMINIMAP_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    settings_version: bpy.props.IntProperty(default=0, options={'HIDDEN'})
    manual_quality: bpy.props.BoolProperty(name="Manual", default=False, update=update_shot_quality)
    background_enabled: bpy.props.BoolProperty(name="Background", default=True)
    background_mode: bpy.props.EnumProperty(
        name="Background Mode",
        items=[('SHELL', 'Automatically Create Walls from Shell', 'Add the existing shell contour walls', 0),
               ('FILL', 'Fill Background', 'Include the existing solid background layer', 1)],
        default='SHELL'
    )
    background_expanded: bpy.props.BoolProperty(name="Background", default=True)
    advanced_expanded: bpy.props.BoolProperty(name="Advanced Settings", default=False)
    ortho_scale_margin: bpy.props.FloatProperty(
        name="Orthographic Scale Margin", subtype='PERCENTAGE', default=1.0, min=0.0, max=100.0)
    camera_clipping_margin: bpy.props.FloatProperty(
        name="Camera Clipping Margin", subtype='PERCENTAGE', default=1.0, min=0.0, max=100.0)
    camera_height_offset: bpy.props.FloatProperty(
        name="Camera Height Offset", subtype='PERCENTAGE', default=10.0, min=0.1, max=99.0)
    auto_hide_collisions: bpy.props.BoolProperty(name="Automatically Hide Collisions", default=True)
    hide_doors: bpy.props.BoolProperty(name="Hide doors", default=True)

    keep_source_svg: bpy.props.BoolProperty(
        name="Keep Source SVG Files",
        description="Keep source SVG files after a successful GFX export",
        default=True
    )

    debug_info: bpy.props.BoolProperty(
        name="Debug Info",
        description="Print minimap diagnostics and external tool output to the console",
        default=False
    )

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
        name="Manual Quality",
        description="Resolution for the minimap shot (pixels)",
        default=2048,
        min=1024,
    )

    shot_quality: bpy.props.EnumProperty(
        name="Map Quality",
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
        row = layout.row()
        row.enabled = not self.manual_quality
        row.prop(self, "shot_quality")
        layout.prop(self, "manual_quality")
        row = layout.row()
        row.enabled = self.manual_quality
        row.prop(self, "shot_resolution")
        layout.prop(self, "author")
        layout.separator()
        box = layout.box()
        box.label(text="Minimap Colors")
        box.prop(self, 'entity_color')
        box.prop(self, 'shell_color')
        box.prop(self, 'background_color', text="Walls")

        layout.separator()
        cbox = layout.box()
        cbox.label(text="Custom Paint")
        cbox.prop(self, 'custom_paint_color')

        layout.prop(self, 'background_enabled')
        box = layout.box()
        box.enabled = self.background_enabled
        box.prop(self, 'background_expanded', icon='TRIA_DOWN' if self.background_expanded else 'TRIA_RIGHT', emboss=False)
        if self.background_expanded:
            box.prop(self, 'background_mode', expand=True)
            row = box.row()
            row.enabled = self.background_mode == 'SHELL'
            row.prop(self, 'wall_thickness')

        box = layout.box()
        box.prop(self, 'advanced_expanded', icon='TRIA_DOWN' if self.advanced_expanded else 'TRIA_RIGHT', emboss=False)
        if self.advanced_expanded:
            box.prop(self, 'ortho_scale_margin')
            box.prop(self, 'camera_clipping_margin')
            box.prop(self, 'camera_height_offset')
        layout.prop(self, 'auto_hide_collisions')
        layout.prop(self, 'hide_doors')
        layout.prop(self, 'keep_source_svg')
        layout.prop(self, 'debug_info')




classes = (GTAMINIMAP_Preferences, GTAMINIMAP_OT_choose_background)
