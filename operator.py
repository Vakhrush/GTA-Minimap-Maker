import bpy
import math


def _clamp_color_tuple(col, length=4):
    """Ensure color tuple components are within 0.0-1.0 and return requested length."""
    if col is None:
        return tuple([0.0] * length)
    # convert to list of floats
    try:
        vals = [float(x) for x in col]
    except Exception:
        vals = [0.0] * length

    # extend or trim
    if len(vals) < length:
        vals = vals + [1.0] * (length - len(vals))
    else:
        vals = vals[:length]

    # clamp
    for i in range(len(vals)):
        v = vals[i]
        if v < 0.0:
            v = 0.0
        if v > 1.0:
            v = 1.0
        vals[i] = v

    return tuple(vals)


def get_object_hierarchy(root_object):
    """Return a flat list of the root object and all its recursive children."""
    if root_object is None:
        return []
    return [root_object, *root_object.children_recursive]


def object_is_sollumz(obj):
    """Heuristic: detect Sollumz-created objects.

    - Ignore cameras, lights, speakers, light probes.
    - For empties: consider Sollumz-only if they have a custom property mentioning 'sollum'.
    - For other object types assume they are props (Sollumz).
    """
    if obj is None:
        return False
    if obj.type in ("CAMERA", "LIGHT", "SPEAKER", "LIGHT_PROBE"):
        return False
    if obj.type == "EMPTY":
        for key in obj.keys():
            try:
                if isinstance(key, str) and "sollum" in key.lower():
                    return True
            except Exception:
                continue
        return False
    return True


def hierarchy_is_sollumz(hierarchy_objects):
    return any(object_is_sollumz(o) for o in hierarchy_objects)


class GTAMINIMAP_OT_prepare_scene(bpy.types.Operator):
    """Refresh Minimap Mode"""
    bl_idname = "gtaminimap.prepare_scene"
    bl_label = "Refresh Minimap Mode"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Ensure single MinimapCam: reuse if exists
        cam_obj = None
        for obj in bpy.data.objects:
            if obj.type == 'CAMERA' and obj.name == 'MinimapCam':
                cam_obj = obj
                break

        if cam_obj is None:
            # create camera
            cam_data = bpy.data.cameras.new(name="MinimapCam")
            cam_data.type = 'ORTHO'
            cam_obj = bpy.data.objects.new("MinimapCam", cam_data)
            # required rotation: X=0, Y=0, Z=0
            cam_obj.rotation_euler = (0.0, 0.0, 0.0)
            cam_obj.lock_rotation[0] = True
            cam_obj.lock_rotation[1] = True
            cam_obj.lock_rotation[2] = True
            # link to scene collection if not linked
            try:
                if cam_obj.name not in context.scene.collection.objects:
                    context.scene.collection.objects.link(cam_obj)
            except Exception:
                try:
                    context.scene.collection.objects.link(cam_obj)
                except Exception:
                    pass
        else:
            # Ensure reused camera has the correct rotation
            try:
                cam_obj.rotation_euler = (0.0, 0.0, 0.0)
            except Exception:
                pass

        # Set as the active scene camera
        try:
            context.scene.camera = cam_obj
        except Exception:
            pass

        # Save original shading settings once per session (window_manager)
        wm = context.window_manager
        wm_key = '_gtaminimap_view_backup_original'
        if wm_key not in wm and wm_key not in context.scene:
            saved_view_settings = []
            for area in context.screen.areas:
                if area.type != 'VIEW_3D':
                    continue

                for space in area.spaces:
                    if space.type != 'VIEW_3D':
                        continue

                    sh = getattr(space, 'shading', None)
                    if sh is not None:
                        sdata = {
                            'light': getattr(sh, 'light', None),
                            'color_type': getattr(sh, 'color_type', None),
                            'background_type': getattr(sh, 'background_type', None) if hasattr(sh, 'background_type') else None,
                            'background_color': _clamp_color_tuple(getattr(sh, 'background_color', (0.0, 0.0, 0.0)), length=3),
                            'show_backface_culling': getattr(sh, 'show_backface_culling', None),
                        }
                    else:
                        sdata = None

                    saved_view_settings.append(sdata)

            try:
                wm[wm_key] = saved_view_settings
            except Exception:
                # fallback to scene-level storage if wm custom props unavailable
                try:
                    context.scene[wm_key] = saved_view_settings
                except Exception:
                    pass

        # Apply required shading changes only
        prefs = None
        try:
            prefs = context.preferences.addons.get(__package__).preferences
        except Exception:
            prefs = None

        if prefs is not None:
            try:
                bg_color = tuple(getattr(prefs, 'background_color', (0.258823543, 0.258823543, 0.258823543, 1.0)))
            except Exception:
                bg_color = (0.258823543, 0.258823543, 0.258823543, 1.0)
        else:
            bg_color = (0.258823543, 0.258823543, 0.258823543, 1.0)

        for area in context.screen.areas:
            if area.type != 'VIEW_3D':
                continue

            for space in area.spaces:
                if space.type != 'VIEW_3D':
                    continue

                sh = getattr(space, 'shading', None)
                if sh is None:
                    continue

                try:
                    sh.light = 'FLAT'
                except Exception:
                    pass

                try:
                    sh.color_type = 'OBJECT'
                except Exception:
                    pass

                try:
                    if hasattr(sh, 'background_type'):
                        # always switch viewport background to the Viewport/Custom mode so background color becomes visible
                        sh.background_type = 'VIEWPORT'
                except Exception:
                    pass

                try:
                    # ensure bg_color components are normalized and within 0.0-1.0
                    c = _clamp_color_tuple(bg_color, length=3)
                    sh.background_color = (c[0], c[1], c[2])
                except Exception:
                    pass

                try:
                    sh.show_backface_culling = True
                except Exception:
                    pass

                try:
                    if hasattr(sh, 'show_cavity'):
                        sh.show_cavity = False
                except Exception:
                    pass

        # Apply entity/shell coloring to Sollumz-linked hierarchies if present
        try:
            prefs = context.preferences.addons.get(__package__).preferences
        except Exception:
            prefs = None

        if prefs is not None:
            try:
                entity_color = tuple(getattr(prefs, 'entity_color', (0.435294, 0.435294, 0.435294, 1.0)))
            except Exception:
                entity_color = (0.435294, 0.435294, 0.435294, 1.0)

            try:
                shell_color = tuple(getattr(prefs, 'shell_color', (0.580392, 0.580392, 0.580392, 1.0)))
            except Exception:
                shell_color = (0.580392, 0.580392, 0.580392, 1.0)

            # clamp colors
            entity_color = _clamp_color_tuple(entity_color, length=4)
            shell_color = _clamp_color_tuple(shell_color, length=4)

            scene = context.scene
            # Traverse ytyps/archetypes/entities if present (Sollumz structure)
            for ytyp in getattr(scene, 'ytyps', []) or []:
                for archetype in getattr(ytyp, 'archetypes', []) or []:
                    for entity in getattr(archetype, 'entities', []) or []:
                        linked = getattr(entity, 'linked_object', None)
                        if linked is None:
                            continue

                        hierarchy = get_object_hierarchy(linked)
                        if not hierarchy:
                            continue

                        # Decide whether this hierarchy should be colored as shell or entity
                        # If any object name contains 'shell' (case-insensitive) -> use shell_color
                        use_shell = False
                        try:
                            for o in hierarchy:
                                name = getattr(o, 'name', '') or ''
                                try:
                                    if 'shell' in name.lower():
                                        use_shell = True
                                        break
                                except Exception:
                                    continue
                        except Exception:
                            use_shell = False

                        color = shell_color if use_shell else entity_color

                        # Apply color to every object in the linked hierarchy
                        for obj in hierarchy:
                            try:
                                if getattr(obj, 'type', None) in ('MESH', 'CURVE', 'SURFACE', 'META') or obj.type == 'EMPTY':
                                    obj.color = (color[0], color[1], color[2], color[3])
                            except Exception:
                                continue

        self.report({'INFO'}, "Minimap mode enabled.")
        return {'FINISHED'}





class GTAMINIMAP_OT_make_shot(bpy.types.Operator):
    """Make Shot"""
    bl_idname = "gtaminimap.make_shot"
    bl_label = "Make Shot"
    bl_options = {'REGISTER'}

    def execute(self, context):
        # Simplified: only render the viewport and save image
        import datetime
        from pathlib import Path

        scene = context.scene

        # find preferences
        def get_addon_preferences(ctx):
            try:
                prefs = ctx.preferences.addons.get(__package__)
                if prefs:
                    return prefs.preferences
            except Exception:
                pass
            for addon_key, addon_module in ctx.preferences.addons.items():
                try:
                    p = addon_module.preferences
                    if hasattr(p, 'shot_resolution') and hasattr(p, 'output_path'):
                        return p
                except Exception:
                    continue
            return None

        prefs = get_addon_preferences(context)

        default_res = 4096
        min_res = 2048
        shot_res = default_res

        if prefs is not None:
            try:
                shot_res = int(getattr(prefs, 'shot_resolution', default_res))
            except Exception:
                shot_res = default_res

        if shot_res < min_res:
            shot_res = min_res

        out_dir = None
        if prefs is not None:
            out_path = getattr(prefs, 'output_path', '')
            if out_path:
                p = Path(bpy.path.abspath(out_path))
                if p.exists() and p.is_dir():
                    out_dir = p

        if out_dir is None:
            try:
                blend_fp = Path(bpy.data.filepath)
                if blend_fp.exists():
                    out_dir = blend_fp.parent
            except Exception:
                out_dir = None

        if out_dir is None:
            try:
                out_dir = Path(__file__).parent
            except Exception:
                out_dir = Path('.')

        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"minimap_{timestamp}.png"
        out_path = out_dir / filename

        scene.render.image_settings.file_format = 'PNG'
        scene.render.resolution_x = shot_res
        scene.render.resolution_y = shot_res
        scene.render.filepath = str(out_path)

        # find 3D view area
        area_for_render = None
        region = None
        space_for_render = None
        for area in context.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            for space in area.spaces:
                if space.type != 'VIEW_3D':
                    continue
                area_for_render = area
                space_for_render = space
                for r in area.regions:
                    if r.type == 'WINDOW':
                        region = r
                        break
                break
            if area_for_render:
                break

        if area_for_render is None or region is None or space_for_render is None:
            self.report({'ERROR'}, "No 3D Viewport found for rendering")
            return {'CANCELLED'}
        # Prepare temporary viewport state: activate MinimapCam, switch to camera view and hide gizmos/overlays
        cam_obj = None
        for obj in bpy.data.objects:
            if obj.type == 'CAMERA' and obj.name == 'MinimapCam':
                cam_obj = obj
                break

        # set scene camera if found
        if cam_obj is not None:
            try:
                context.scene.camera = cam_obj
            except Exception:
                pass

        # save previous UI state to restore after render
        prev_show_gizmo = getattr(space_for_render, 'show_gizmo', None)
        prev_overlay_show = None
        try:
            if hasattr(space_for_render, 'overlay') and space_for_render.overlay is not None:
                prev_overlay_show = space_for_render.overlay.show_overlays
        except Exception:
            prev_overlay_show = None

        prev_view_perspective = None
        try:
            if hasattr(space_for_render, 'region_3d') and space_for_render.region_3d is not None:
                prev_view_perspective = getattr(space_for_render.region_3d, 'view_perspective', None)
        except Exception:
            prev_view_perspective = None

        # apply temporary changes
        try:
            try:
                if hasattr(space_for_render, 'region_3d') and space_for_render.region_3d is not None:
                    space_for_render.region_3d.view_perspective = 'CAMERA'
            except Exception:
                pass

            try:
                if prev_show_gizmo is not None:
                    space_for_render.show_gizmo = False
            except Exception:
                pass

            try:
                if prev_overlay_show is not None and hasattr(space_for_render, 'overlay'):
                    space_for_render.overlay.show_overlays = False
            except Exception:
                pass

            # perform OpenGL viewport render in the 3D view context
            try:
                if hasattr(context, 'temp_override'):
                    with context.temp_override(window=context.window, area=area_for_render, region=region, space=space_for_render):
                        bpy.ops.render.opengl(write_still=True)
                else:
                    override = {'window': context.window, 'screen': context.screen, 'area': area_for_render, 'region': region, 'scene': scene}
                    bpy.ops.render.opengl(override, write_still=True)
            except Exception as e:
                self.report({'ERROR'}, f"OpenGL render failed: {e}")
                return {'CANCELLED'}
        finally:
            # restore temporary UI state
            try:
                if prev_show_gizmo is not None:
                    space_for_render.show_gizmo = prev_show_gizmo
            except Exception:
                pass

            try:
                if prev_overlay_show is not None and hasattr(space_for_render, 'overlay'):
                    space_for_render.overlay.show_overlays = prev_overlay_show
            except Exception:
                pass

            try:
                if prev_view_perspective is not None and hasattr(space_for_render, 'region_3d') and space_for_render.region_3d is not None:
                    space_for_render.region_3d.view_perspective = prev_view_perspective
            except Exception:
                pass

        try:
            if out_path.exists():
                self.report({'INFO'}, f"Minimap saved to: {out_path}")
            else:
                self.report({'ERROR'}, f"Minimap render did not produce file: {out_path}")
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Error verifying save: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}





class GTAMINIMAP_OT_exit_minimap_mode(bpy.types.Operator):
    """Restore viewport display settings saved by Make Shot For Minimap"""
    bl_idname = "gtaminimap.exit_minimap_mode"
    bl_label = "Exit Minimap Mode"
    bl_options = {'REGISTER'}

    def execute(self, context):
        # Restore only selected shading settings from the session backup saved in window_manager
        wm = context.window_manager
        wm_key = '_gtaminimap_view_backup_original'

        saved = None
        if wm_key in wm:
            saved = wm[wm_key]
        else:
            # fallback to scene-level storage
            saved = context.scene.get(wm_key)

        if not saved:
            self.report({'WARNING'}, "No minimap viewport state found.")
            return {'CANCELLED'}

        # saved is a list aligned with VIEW_3D spaces order; restore only specified shading fields
        idx = 0
        for area in context.screen.areas:
            if area.type != 'VIEW_3D':
                continue

            for space in area.spaces:
                if space.type != 'VIEW_3D':
                    continue

                if idx >= len(saved):
                    break

                sdata = saved[idx]
                idx += 1

                sh = getattr(space, 'shading', None)
                if sh is not None and sdata:
                    try:
                        if sdata.get('light') is not None:
                            sh.light = sdata.get('light')
                    except Exception:
                        pass

                    try:
                        if sdata.get('color_type') is not None:
                            sh.color_type = sdata.get('color_type')
                    except Exception:
                        pass

                    try:
                        if sdata.get('background_type') is not None and hasattr(sh, 'background_type'):
                            sh.background_type = sdata.get('background_type')
                    except Exception:
                        pass

                    try:
                        if sdata.get('background_color') is not None:
                            col = sdata.get('background_color')
                            # ensure 3-element RGB tuple where API expects
                            if hasattr(sh, 'background_color'):
                                sh.background_color = (col[0], col[1], col[2])
                    except Exception:
                        pass

                    try:
                        if sdata.get('show_backface_culling') is not None:
                            sh.show_backface_culling = sdata.get('show_backface_culling')
                    except Exception:
                        pass

        self.report({'INFO'}, "Minimap mode disabled.")
        return {'FINISHED'}


class GTAMINIMAP_OT_apply_color_selected(bpy.types.Operator):
    """Apply custom paint color to selected mesh objects"""
    bl_idname = "gtaminimap.apply_color_selected"
    bl_label = "Apply Color To Selected Meshes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        prefs = None
        try:
            prefs = context.preferences.addons.get(__package__).preferences
        except Exception:
            prefs = None

        if prefs is None:
            # Fallback: search addons for preferences that expose the expected setting
            try:
                for addon_key, addon_module in context.preferences.addons.items():
                    p = getattr(addon_module, 'preferences', None)
                    if p is not None and hasattr(p, 'custom_paint_color'):
                        prefs = p
                        break
            except Exception:
                prefs = None

        if prefs is None:
            self.report({'ERROR'}, "Addon preferences not found.")
            return {'CANCELLED'}

        color = tuple(getattr(prefs, 'custom_paint_color', (1.0, 1.0, 1.0, 1.0)))

        selected = context.selected_objects
        mesh_objs = [o for o in selected if getattr(o, 'type', None) == 'MESH']

        if not mesh_objs:
            self.report({'WARNING'}, "Please select one or more mesh objects.")
            return {'CANCELLED'}

        for obj in mesh_objs:
            try:
                c = _clamp_color_tuple(color, length=4)
                obj.color = (c[0], c[1], c[2], c[3])
            except Exception:
                pass

        self.report({'INFO'}, f"Applied custom paint color to {len(mesh_objs)} mesh object(s).")
        return {'FINISHED'}
classes = (
    GTAMINIMAP_OT_prepare_scene,
    GTAMINIMAP_OT_make_shot,
    GTAMINIMAP_OT_apply_color_selected,
    GTAMINIMAP_OT_exit_minimap_mode,
)
