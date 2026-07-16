import bpy


class GTAMINIMAP_PT_panel(bpy.types.Panel):
    bl_label = "GTA Minimap Maker"
    bl_idname = "GTAMINIMAP_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GTA Tools'

    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)
        row.label(text="Number of floors:")
        row.prop(context.scene, "minimap_floors", text="")
        row.operator("gtaminimap.floor_mapping_help", text="", icon='QUESTION')
        layout.prop(context.scene, "has_basement", text="Has basement")
        layout.separator()
        layout.operator('gtaminimap.prepare_scene', icon='SCENE')
        layout.operator('gtaminimap.exit_minimap_mode', icon='LOOP_BACK')

        # Preferences-based color quick settings (read-only here; main settings in Add-on Preferences)
        layout.separator()
        box = layout.box()
        box.label(text="Minimap Colors")
        prefs = context.preferences.addons.get(__package__)
        if prefs:
            p = prefs.preferences
            row = box.row()
            row.prop(p, 'entity_color', text='Entity')
            row = box.row()
            row.prop(p, 'shell_color', text='Shell')
            row = box.row()
            row.prop(p, 'background_color', text='Walls')
            layout.operator("gtaminimap.reset_colors", text="Reset Minimap Colors", icon='FILE_REFRESH')

            # separate custom paint into its own section (single label)
            layout.separator()
            cbox = layout.box()
            cbox.prop(p, 'custom_paint_color', text='Custom Paint')
            cbox.operator('gtaminimap.apply_color_selected', icon='BRUSH_DATA')
        else:
            box.label(text="Open Add-on Preferences to configure colors")

        # export settings
        layout.separator()
        layout.prop(context.scene, "mlo_name", text="MLO Name")

        # final step
        layout.separator()
        layout.operator('gtaminimap.make_shot', icon='RENDER_STILL')


classes = (GTAMINIMAP_PT_panel,)
