import bpy
import math
import subprocess
from pathlib import Path
import shutil
import re

def joaat(text):
    text = text.lower()

    h = 0

    for c in text:
        h += ord(c)
        h &= 0xFFFFFFFF

        h += (h << 10)
        h &= 0xFFFFFFFF

        h ^= (h >> 6)

    h += (h << 3)
    h &= 0xFFFFFFFF

    h ^= (h >> 11)

    h += (h << 15)
    h &= 0xFFFFFFFF

    return h

def build_gfx(target_dir, mlo_name):
    temp_swf = target_dir / "intEXAMPLE.swf"
    temp_xml = target_dir / "intEXAMPLE.xml"

    for f in (temp_swf, temp_xml):
        try:
            if f.exists():
                f.unlink()
                print(f"[GFX] Removed old temp: {f}")
        except Exception as e:
            print(f"[GFX] Cannot remove {f}: {e}")

    hash_value = joaat(mlo_name)

    addon_dir = Path(__file__).parent

    template_gfx = Path(__file__).parent / "intEXAMPLE.gfx"

    temp_swf = target_dir / "intEXAMPLE.swf"
    temp_xml = target_dir / "intEXAMPLE.xml"

    final_gfx = target_dir / f"int{hash_value}.gfx"

    prefs = bpy.context.preferences.addons[__package__].preferences

    ffdec = Path(
        bpy.path.abspath(prefs.jpexs_path)
    ) / "ffdec-cli.exe"

    shutil.copy2(template_gfx, temp_swf)

    if not ffdec.exists():
        raise Exception(
            f"FFDec not found: {ffdec}"
        )

    subprocess.run(
        [
            str(ffdec),
            "-swf2xml",
            str(temp_swf),
            str(temp_xml)
        ],
        check=True
    )

    with open(temp_xml, "r", encoding="utf-8") as f:
        xml = f.read()

    xml = xml.replace("col_name", mlo_name)
    xml = xml.replace("EXAMPLE", str(hash_value))

    ortho = bpy.context.scene.camera.data.ortho_scale

    # ---------- TranslateX&TranslateY ----------

    move = int(round(-(97.75 * ortho + 50.0)))

    pattern = (
        r'(<item type="PlaceObject2Tag" characterId="1".*?'
        r'<matrix[^>]*translateX=")-?\d+(\.\d+)?'
        r'(" translateY=")-?\d+(\.\d+)?(")'
    )

    xml = re.sub(
        pattern,
        rf'\g<1>{move}\g<3>{move}\g<5>',
        xml,
        flags=re.DOTALL
    )

    # ---------- Scale ----------

    scale = 0.00468018 * ortho + 0.002236

    pattern = (
        r'(<item type="PlaceObject2Tag" characterId="1".*?'
        r'scaleX=")-?\d+(\.\d+)?'
        r'(" scaleY=")-?\d+(\.\d+)?(")'
    )

    xml = re.sub(
        pattern,
        rf'\g<1>{scale:.8f}\g<3>{scale:.8f}\g<5>',
        xml,
        flags=re.DOTALL
    )

    print(f"[GFX] translate = {move}")
    print(f"[GFX] scale = {scale:.8f}")

    with open(temp_xml, "w", encoding="utf-8") as f:
        f.write(xml)

    subprocess.run(
        [
            str(ffdec),
            "-xml2swf",
            str(temp_xml),
            str(temp_swf)
        ],
        check=True
    )

    svg_file = target_dir / "1.svg"

    if svg_file.exists():
        subprocess.run(
            [
                str(ffdec),
                "-importShapes",
                str(temp_swf),
                str(temp_swf),
                str(target_dir),
            ],
            check=True
        )

        print("[GFX] Shape imported")
    else:
        raise Exception(f"SVG not found: {svg_file}")

    if final_gfx.exists():
        final_gfx.unlink()

    temp_swf.rename(final_gfx)

    if temp_xml.exists():
        temp_xml.unlink()

    print(f"[GFX] Created: {final_gfx}")

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


def _save_potrace_ready(png_path, out_path, bg_color):
    """Create a Potrace-ready black/white file from a PNG.

    - png_path: Path to source PNG
    - out_path: Path to output file (with desired extension)
    - bg_color: tuple(r,g,b,a)
    - is_background: if True, pixels that are visible become black (background layer)
    """
    try:
        print(f"[Potrace] _save_potrace_ready start: png_path={png_path}, out_path={out_path}")
        img = None
        fp = str(png_path)
        # remove existing loaded image if any
        for existing in bpy.data.images:
            try:
                if getattr(existing, 'filepath', '') == fp or getattr(existing, 'filepath_raw', '') == fp:
                    img = existing
                    break
            except Exception:
                continue

        if img is None:
            try:
                print(f"[Potrace] loading image: {fp}")
                img = bpy.data.images.load(fp)
                print(f"[Potrace] image loaded: {fp}")
            except Exception as e:
                print(f"[Potrace] image load error: {e}")
                return False

        width = img.size[0]
        height = img.size[1]
        channels = img.channels
        pixels = list(img.pixels[:])

        # Build binary mask: True for object (black), False for background (white)
        mask = [False] * (width * height)
        eps = 1e-6
        for y in range(height):
            for x in range(width):
                idx = (y * width + x) * channels
                try:
                    if channels >= 4:
                        a = pixels[idx + 3]
                        # If alpha present, use it to determine foreground
                        present = (a > 0.5)
                    else:
                        r = pixels[idx]
                        g = pixels[idx + 1]
                        b = pixels[idx + 2]
                        # compare to background color: if equal => background (False), else foreground (True)
                        present = not (abs(r - bg_color[0]) <= eps and abs(g - bg_color[1]) <= eps and abs(b - bg_color[2]) <= eps)
                except Exception:
                    present = False

                mask[y * width + x] = bool(present)

        # Output
        with open(out_path, 'wb') as f:
            header = f"P4\n{width} {height}\n".encode('ascii')
            f.write(header)

            for y in reversed(range(height)):
                byte = 0
                bits = 0

                for x in range(width):
                    m = mask[y * width + x]

                    bit = 1 if m else 0

                    byte = (byte << 1) | bit
                    bits += 1

                    if bits == 8:
                        f.write(bytes([byte]))
                        byte = 0
                        bits = 0

                if bits > 0:
                    byte <<= (8 - bits)
                    f.write(bytes([byte]))


        # cleanup loaded image
        try:
            if img is not None:
                bpy.data.images.remove(img)
                print(f"[Potrace] removed loaded image: {fp}")
        except Exception as e:
            print(f"Potrace export error: {e}")

        print(f"[Potrace] _save_potrace_ready end: out_path={out_path}")

        return True
    except Exception:
        return False


def export_potrace_ready_files(target_dir, layer_names, bg_color):
    """Export Potrace-ready PBM files for Potrace."""
    print(f"[Potrace] export_potrace_ready_files called with target_dir={target_dir}")

    results = {}

    for name in layer_names:
        try:
            print(f"[Potrace] start export for layer: {name}")

            png_fp = target_dir / f"{name}.png"
            out_fp = target_dir / f"{name}.pbm"

            print(f"[Potrace] Potrace output path: {out_fp}")

            is_bg = (name.lower() == "background")

            ok = _save_potrace_ready(
                png_fp,
                out_fp,
                bg_color,
            )

            results[name] = ok

            print(f"[Potrace] export result for {name}: {ok}")

        except Exception as e:
            print(f"Potrace export error: {e}")
            results[name] = False

    return results


def run_potrace(pbm_path, svg_path):
    try:
        potrace_path = Path(__file__).parent / "potrace.exe"

        subprocess.run(
            [
                str(potrace_path),
                str(pbm_path),
                "-s",
                "--alphamax", "1.0",
                "--opttolerance", "2.0",
                "--turdsize", "20",
                "-o",
                str(svg_path)
            ],
            check=True
        )

        print(f"[Potrace] SVG created: {svg_path}")
        return True

    except Exception as e:
        print(f"[Potrace] Error: {e}")
        return False


def linear_to_srgb(c):
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * (c ** (1.0 / 2.4)) - 0.055


def svg_color_to_hex(color):
    r = int(round(linear_to_srgb(color[0]) * 255))
    g = int(round(linear_to_srgb(color[1]) * 255))
    b = int(round(linear_to_srgb(color[2]) * 255))

    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))

    return f"#{r:02X}{g:02X}{b:02X}"


def recolor_svg(svg_path, color):
    try:
        hex_color = svg_color_to_hex(color)

        with open(svg_path, "r", encoding="utf-8") as f:
            content = f.read()

        content = content.replace(
            'fill="#000000"',
            f'fill="{hex_color}"'
        )

        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"[SVG] Recolored: {svg_path} -> {hex_color}")

    except Exception as e:
        print(f"[SVG] Recolor error: {e}")


def merge_svg_layers(svg_files, output_svg):
    try:
        all_groups = []

        viewbox = "0 0 2048 2048"

        for svg_file in svg_files:
            if not svg_file.exists():
                continue

            with open(svg_file, "r", encoding="utf-8") as f:
                content = f.read()

            import re

            vb = re.search(r'viewBox="([^"]+)"', content)
            if vb:
                viewbox = vb.group(1)

            groups = re.findall(
                r"<g.*?</g>",
                content,
                flags=re.DOTALL
            )

            all_groups.extend(groups)

        with open(output_svg, "w", encoding="utf-8") as f:
            f.write(
f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
viewBox="{viewbox}">
'''
            )

            for group in all_groups:
                f.write(group + "\n")

            f.write("</svg>\n")

        print(f"[SVG] Merged: {output_svg}")

    except Exception as e:
        print(f"[SVG] Merge error: {e}")


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

        floors = int(context.scene.minimap_floors)

        # Remove unnecessary Minimap cameras
        for obj in list(bpy.data.objects):
            if obj.type != 'CAMERA':
                continue

            if not obj.name.startswith("MinimapCam_"):
                continue

            try:
                number = int(
                    obj.name.replace("MinimapCam_", "").replace("floor", "")
                )
            except Exception:
                continue

            if number > floors:
                bpy.data.objects.remove(obj, do_unlink=True)

        # Create / update cameras
        first_camera = None

        for floor in range(floors):

            cam_name = f"MinimapCam_{floor + 1}floor"

            cam_obj = bpy.data.objects.get(cam_name)

            if cam_obj is None:

                cam_data = bpy.data.cameras.new(name=cam_name)
                cam_data.type = 'ORTHO'

                cam_obj = bpy.data.objects.new(cam_name, cam_data)
                context.scene.collection.objects.link(cam_obj)

            cam_obj.location = (
                0.0,
                0.0,
                float(floor)
            )

            cam_obj.rotation_euler = (
                0.0,
                0.0,
                0.0
            )

            cam_obj.lock_rotation[0] = True
            cam_obj.lock_rotation[1] = True
            cam_obj.lock_rotation[2] = True

            cam_obj.lock_location[0] = True
            cam_obj.lock_location[1] = True
            cam_obj.lock_location[2] = False

            if floor == 0:
                first_camera = cam_obj

        # Set first camera as active
        if first_camera is not None:
            context.scene.camera = first_camera

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
                bg_color = tuple(getattr(prefs, 'background_color', (66.0/255.0, 66.0/255.0, 66.0/255.0, 1.0)))
            except Exception:
                bg_color = (66.0/255.0, 66.0/255.0, 66.0/255.0, 1.0)
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
                entity_color = tuple(getattr(prefs, 'entity_color', (111.0/255.0, 111.0/255.0, 111.0/255.0, 1.0)))
            except Exception:
                entity_color = (111.0/255.0, 111.0/255.0, 111.0/255.0, 1.0)

            try:
                shell_color = tuple(getattr(prefs, 'shell_color', (148.0/255.0, 148.0/255.0, 148.0/255.0, 1.0)))
            except Exception:
                shell_color = (148.0/255.0, 148.0/255.0, 148.0/255.0, 1.0)

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

        if prefs is not None:
            shot_res = prefs.shot_resolution
        else:
            shot_res = 2048

        context.scene.render.resolution_x = shot_res
        context.scene.render.resolution_y = shot_res

        self.report({'INFO'}, "Minimap mode enabled.")
        return {'FINISHED'}


class GTAMINIMAP_OT_make_shot(bpy.types.Operator):
    """Make Shot"""
    bl_idname = "gtaminimap.make_shot"
    bl_label = "Make Shot"
    bl_options = {'REGISTER'}

    def export_floor(self, context, scene, prefs, target_dir, out_path, area_for_render, region, space_for_render, svg_index):
        timestamp = None

        # Validate active scene camera before starting
        cam_obj = context.scene.camera

        if cam_obj is None:
            self.report({'WARNING'}, "Active camera not found.")
            return {'CANCELLED'}

        if getattr(cam_obj, 'type', None) != 'CAMERA':
            self.report({'WARNING'}, "Active camera is not a camera object.")
            return {'CANCELLED'}

        if not getattr(cam_obj, 'name', '').startswith('MinimapCam_'):
            self.report({'WARNING'}, "Active camera must start with MinimapCam_.")
            return {'CANCELLED'}

        # Check Camera Shift <= 0
        cam_data = cam_obj.data

        eps = 1e-6

        if abs(cam_data.shift_x) > eps or abs(cam_data.shift_y) > eps:
            cam_data.shift_x = 0.0
            cam_data.shift_y = 0.0

            self.report(
                {'WARNING'},
                "Camera Shift is not supported. Shift X and Y have been reset."
            )

            return {'CANCELLED'}

        # Check Camera Transform
        loc = cam_obj.location
        rot = cam_obj.rotation_euler

        if (
            abs(loc.x) > eps or
            abs(loc.y) > eps or
            abs(rot.x) > eps or
            abs(rot.y) > eps or
            abs(rot.z) > eps
        ):
            cam_obj.location.x = 0.0
            cam_obj.location.y = 0.0
            cam_obj.rotation_euler = (0.0, 0.0, 0.0)

            self.report(
                {'WARNING'},
                "Camera transform is invalid. Location X/Y and Rotation have been reset."
            )

            return {'CANCELLED'}

        # Check current 3D view is in camera view
        try:
            current_persp = None
            if hasattr(space_for_render, 'region_3d') and space_for_render.region_3d is not None:
                current_persp = getattr(space_for_render.region_3d, 'view_perspective', None)
        except Exception:
            current_persp = None

        if current_persp != 'CAMERA':
            self.report({'WARNING'}, "Enable Toggle Camera View before making a shot.")
            return {'CANCELLED'}
        # Prepare temporary viewport state: activate active scene camera, switch to camera view and hide gizmos/overlays
        cam_obj = context.scene.camera

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
                    render_override = context.temp_override(window=context.window, area=area_for_render, region=region, space=space_for_render)
                else:
                    render_override = None

                if render_override is not None:
                    render_ctx = render_override
                else:
                    render_ctx = None

                # save original film_transparent setting and force transparent film for layer renders when needed
                orig_film_transparent = getattr(scene.render, 'film_transparent', False)

                if render_ctx is not None:
                    with render_ctx:
                        bpy.ops.render.opengl(write_still=True)
                else:
                    override = {'window': context.window, 'screen': context.screen, 'area': area_for_render, 'region': region, 'scene': scene}
                    bpy.ops.render.opengl(override, write_still=True)
            except Exception as e:
                self.report({'ERROR'}, f"OpenGL render failed: {e}")
                raise

            try:
                try:
                    entity_color = _clamp_color_tuple(tuple(getattr(prefs, 'entity_color', (111.0/255.0, 111.0/255.0, 111.0/255.0, 1.0))), length=4)
                except Exception:
                    entity_color = _clamp_color_tuple((111.0/255.0, 111.0/255.0, 111.0/255.0, 1.0), length=4)

                try:
                    shell_color = _clamp_color_tuple(tuple(getattr(prefs, 'shell_color', (148.0/255.0, 148.0/255.0, 148.0/255.0, 1.0))), length=4)
                except Exception:
                    shell_color = _clamp_color_tuple((148.0/255.0, 148.0/255.0, 148.0/255.0, 1.0), length=4)

                try:
                    bg_color = _clamp_color_tuple(tuple(getattr(prefs, 'background_color', (66.0/255.0, 66.0/255.0, 66.0/255.0, 1.0))), length=4)
                except Exception:
                    bg_color = _clamp_color_tuple((66.0/255.0, 66.0/255.0, 66.0/255.0, 1.0), length=4)

                scene = context.scene

                all_objects = list(bpy.data.objects)
                orig_states = {}
                for obj in all_objects:
                    orig_states[obj.name] = {
                        'hide_viewport': getattr(obj, 'hide_viewport', False),
                        'hide_render': getattr(obj, 'hide_render', False),
                        'color': _clamp_color_tuple(tuple(getattr(obj, 'color', (1.0, 1.0, 1.0, 1.0))), length=4)
                    }

                shell_set = set()
                custom_set = set()
                entity_set = set()
                walls_set = set()

                def color_matches(a, b, eps=1e-6):
                    try:
                        for i in range(3):
                            if abs(a[i] - b[i]) > eps:
                                return False
                    except Exception:
                        return False
                    return True

                for obj in all_objects:
                    try:
                        if getattr(obj, 'type', None) not in ('MESH', 'CURVE', 'SURFACE', 'META') and obj.type != 'EMPTY':
                            continue
                    except Exception:
                        continue

                    col = orig_states.get(obj.name, {}).get('color', (1.0, 1.0, 1.0, 1.0))

                    if color_matches(col, bg_color):
                        walls_set.add(obj)
                    elif color_matches(col, shell_color):
                        shell_set.add(obj)
                    elif color_matches(col, entity_color):
                        entity_set.add(obj)
                    else:
                        custom_set.add(obj)

                def render_layer(filename_path, visible_objs, transparent=True, opaque_bg=False, bg_override=None):
                    scene.render.filepath = str(filename_path)
                    print(f"[Render] render_layer start: {filename_path}, transparent={transparent}, bg_override={bg_override}")
                    try:
                        if transparent:
                            scene.render.image_settings.color_mode = 'RGBA'
                        else:
                            scene.render.image_settings.color_mode = 'RGB'
                    except Exception:
                        pass
                    sh = None
                    orig_sh_bg = None
                    try:
                        if bg_override is not None and hasattr(space_for_render, 'shading'):
                            sh = getattr(space_for_render, 'shading')
                            if sh is not None and hasattr(sh, 'background_color'):
                                try:
                                    orig_sh_bg = tuple(getattr(sh, 'background_color'))
                                except Exception:
                                    orig_sh_bg = None
                                try:
                                    sh.background_color = (bg_override[0], bg_override[1], bg_override[2])
                                except Exception:
                                    pass
                    except Exception:
                        sh = None
                    try:
                        for o in all_objects:
                            try:
                                o.hide_viewport = True
                            except Exception:
                                pass
                    except Exception:
                        pass

                    try:
                        for o in visible_objs:
                            try:
                                o.hide_viewport = False
                            except Exception:
                                pass
                    except Exception:
                        pass

                    try:
                        if transparent:
                            try:
                                scene.render.film_transparent = True
                            except Exception:
                                pass
                        else:
                            try:
                                scene.render.film_transparent = False
                            except Exception:
                                pass
                    except Exception:
                        pass

                    try:
                        print(f"[Render] performing OpenGL render to {filename_path}")
                        if render_ctx is not None:
                            with render_ctx:
                                bpy.ops.render.opengl(write_still=True)
                        else:
                            override = {'window': context.window, 'screen': context.screen, 'area': area_for_render, 'region': region, 'scene': scene}
                            bpy.ops.render.opengl(override, write_still=True)
                        print(f"[Render] OpenGL render complete for {filename_path}")
                    except Exception:
                        raise
                    finally:
                        try:
                            for o in all_objects:
                                st = orig_states.get(o.name)
                                if st is not None:
                                    try:
                                        o.hide_viewport = st.get('hide_viewport', False)
                                    except Exception:
                                        pass
                        except Exception:
                            pass

                    try:
                        if transparent and filename_path is not None:
                            print(f"[Render] post-process start for {filename_path}")
                            try:
                                if filename_path.name.lower() != 'background.png':
                                    try:
                                        img = None
                                        fp_str = str(filename_path)
                                        for existing in bpy.data.images:
                                            try:
                                                if existing.filepath == fp_str:
                                                    img = existing
                                                    break
                                            except Exception:
                                                continue
                                        if img is None:
                                            img = bpy.data.images.load(fp_str)

                                        if img.channels < 4:
                                            try:
                                                img.use_alpha = True
                                            except Exception:
                                                pass

                                        pixels = list(img.pixels[:])
                                        changed = False
                                        eps = 1e-6
                                        try:
                                            if bg_override is not None:
                                                bg = (bg_override[0], bg_override[1], bg_override[2], 1.0)
                                            else:
                                                bg = bg_color
                                        except Exception:
                                            bg = (0.0, 0.0, 0.0, 1.0)

                                        for i in range(0, len(pixels), img.channels):
                                            try:
                                                r = pixels[i]
                                                g = pixels[i+1]
                                                b = pixels[i+2]
                                            except Exception:
                                                continue

                                            if abs(r - bg[0]) <= eps and abs(g - bg[1]) <= eps and abs(b - bg[2]) <= eps:
                                                if img.channels >= 4:
                                                    if pixels[i+3] != 0.0:
                                                        pixels[i+3] = 0.0
                                                        changed = True

                                        if changed:
                                            try:
                                                img.pixels[:] = pixels
                                                img.filepath_raw = fp_str
                                                img.file_format = 'PNG'
                                                img.save()
                                            except Exception:
                                                pass

                                        try:
                                            if img is not None:
                                                bpy.data.images.remove(img)
                                                print(f"[Render] removed loaded image after postprocess: {fp_str}")
                                        except Exception:
                                            pass
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            print(f"[Render] post-process end for {filename_path}")
                    except Exception:
                        pass

                    try:
                        if sh is not None and orig_sh_bg is not None:
                            try:
                                sh.background_color = orig_sh_bg
                            except Exception:
                                pass
                    except Exception:
                        pass

                try:
                    background_fp = target_dir / 'background.png'
                    render_layer(background_fp, [], transparent=False, opaque_bg=True)
                except Exception:
                    pass

                try:
                    shell_fp = target_dir / 'shell.png'
                    render_layer(shell_fp, shell_set, transparent=True)
                except Exception:
                    pass

                try:
                    entity_fp = target_dir / 'entity.png'
                    render_layer(entity_fp, entity_set, transparent=True)
                except Exception:
                    pass

                try:
                    walls_fp = target_dir / 'walls.png'
                    render_layer(walls_fp, walls_set, transparent=True, bg_override=(1.0, 0.0, 1.0))
                except Exception:
                    pass

                try:
                    custom_fp = target_dir / 'custom.png'
                    render_layer(custom_fp, custom_set, transparent=True)
                except Exception:
                    pass

                self.report({'INFO'}, "Layered PNG export completed.")

                try:
                    layer_names = ['background', 'shell', 'entity', 'walls', 'custom']

                    bg_c = (0.0, 0.0, 0.0, 1.0)

                    try:
                        if prefs is not None:
                            bg_c = _clamp_color_tuple(
                                getattr(prefs, 'background_color', bg_c),
                                4
                            )
                    except Exception:
                        pass

                    export_potrace_ready_files(
                        target_dir,
                        layer_names,
                        bg_c
                    )

                    for layer in layer_names:
                        pbm_fp = target_dir / f"{layer}.pbm"
                        svg_fp = target_dir / f"{layer}.svg"

                        if pbm_fp.exists():
                            if run_potrace(pbm_fp, svg_fp):
                                if layer == "background":
                                    recolor_svg(svg_fp, bg_color)
                                elif layer == "shell":
                                    recolor_svg(svg_fp, shell_color)
                                elif layer == "entity":
                                    recolor_svg(svg_fp, entity_color)
                                elif layer == "walls":
                                    recolor_svg(svg_fp, bg_color)
                                elif layer == "custom":
                                    recolor_svg(svg_fp, (1.0, 1.0, 1.0, 1.0))

                    final_svg = target_dir / f"{svg_index}.svg"

                    merge_svg_layers(
                        [
                            target_dir / "background.svg",
                            target_dir / "shell.svg",
                            target_dir / "entity.svg",
                            target_dir / "walls.svg",
                            target_dir / "custom.svg",
                        ],
                        final_svg
                    )
                    try:
                        mlo_name = context.scene.mlo_name.strip()

                        if mlo_name:
                            build_gfx(target_dir, mlo_name)

                    except Exception as e:
                        print(f"[GFX] Error: {e}")

                    for layer in layer_names:
                        try:
                            svg_fp = target_dir / f"{layer}.svg"

                            if svg_fp.exists():
                                svg_fp.unlink()
                                print(f"[Cleanup] Removed: {svg_fp}")

                        except Exception as e:
                            print(f"[Cleanup] SVG remove error: {e}")

                    for layer in layer_names:
                        try:
                            png_fp = target_dir / f"{layer}.png"

                            if png_fp.exists():
                                png_fp.unlink()
                                print(f"[Cleanup] Removed: {png_fp}")

                        except Exception as e:
                            print(f"[Cleanup] PNG remove error: {e}")

                    for layer in layer_names:
                        try:
                            pbm_fp = target_dir / f"{layer}.pbm"

                            if pbm_fp.exists():
                                pbm_fp.unlink()
                                print(f"[Cleanup] Removed: {pbm_fp}")

                        except Exception as e:
                            print(f"[Cleanup] PBM remove error: {e}")

                except Exception as e:
                    print(f"Potrace export error: {e}")

            except Exception:
                pass
        finally:
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

    def execute(self, context):
        import datetime
        from pathlib import Path

        scene = context.scene

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

        default_res = 2048
        min_res = 1024
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
        try:
            blend_fp = Path(bpy.data.filepath)
            blend_name = blend_fp.stem if blend_fp.exists() else None
        except Exception:
            blend_name = None

        if not blend_name:
            blend_name = 'Untitled'

        target_dir = out_dir / f"Minimap_{blend_name}"
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        filename = f"minimap_{timestamp}.png"
        out_path = target_dir / filename

        scene.render.image_settings.file_format = 'PNG'
        scene.render.resolution_x = shot_res
        scene.render.resolution_y = shot_res
        scene.render.filepath = str(out_path)

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

        floor_cameras = []
        for obj in bpy.data.objects:
            if getattr(obj, 'type', None) != 'CAMERA':
                continue
            name = getattr(obj, 'name', '')
            if not name.startswith('MinimapCam_') or not name.endswith('floor'):
                continue
            try:
                floor_index = int(name[len('MinimapCam_'):-len('floor')])
            except Exception:
                continue
            floor_cameras.append((floor_index, obj))

        floor_cameras.sort(key=lambda item: item[0])

        result = {'FINISHED'}
        for floor_index, cam_obj in floor_cameras:
            try:
                context.scene.camera = cam_obj
            except Exception:
                pass

            result = self.export_floor(
                context,
                scene,
                prefs,
                target_dir,
                out_path,
                area_for_render,
                region,
                space_for_render,
                floor_index * 2 - 1,
            )

            if result != {'FINISHED'}:
                return result

        return result


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
                print("CUSTOM PREF:", color)
                print("AFTER CLAMP:", c)
                obj.color = (c[0], c[1], c[2], c[3])
            except Exception:
                pass

        self.report({'INFO'}, f"Applied custom paint color to {len(mesh_objs)} mesh object(s).")
        return {'FINISHED'}


class GTAMINIMAP_OT_reset_colors(bpy.types.Operator):
    """Reset Minimap Colors"""
    bl_idname = "gtaminimap.reset_colors"
    bl_label = "Reset Minimap Colors"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            prefs = context.preferences.addons[__package__].preferences
        except Exception:
            self.report({'ERROR'}, "Addon preferences not found.")
            return {'CANCELLED'}

        # linear values for:
        # Entity     #6F6F6F
        # Shell      #949494
        # Background #424242

        prefs.entity_color = (
            0.158961,
            0.158961,
            0.158961,
            1.0
        )

        prefs.shell_color = (
            0.302126,
            0.302126,
            0.302126,
            1.0
        )

        prefs.background_color = (
            0.051269,
            0.051269,
            0.051269,
            1.0
        )

        self.report({'INFO'}, "Minimap colors reset.")
        return {'FINISHED'}
classes = (
    GTAMINIMAP_OT_prepare_scene,
    GTAMINIMAP_OT_make_shot,
    GTAMINIMAP_OT_apply_color_selected,
    GTAMINIMAP_OT_exit_minimap_mode,
    GTAMINIMAP_OT_reset_colors,
)
