"""Camera centering from evaluated MLO geometry clipped to a world-space Z slab."""

import math
from contextlib import contextmanager


@contextmanager
def temporary_mlo_visibility(context, debug):
    """Reveal a hidden MLO hierarchy for measurement and restore every changed flag."""
    name = context.scene.mlo_name.strip()
    root = context.scene.objects.get(name) if name else None
    if root is None or root.visible_get(view_layer=context.view_layer):
        yield
        return
    objects = [obj for obj in (root, *root.children_recursive) if obj.name in context.scene.objects]
    collections = {collection for obj in objects for collection in obj.users_collection}
    paths = []

    def visit(layer, path):
        path = [*path, layer]
        if layer.collection in collections:
            paths.append(path)
        for child in layer.children:
            visit(child, path)

    visit(context.view_layer.layer_collection, [])
    changes = []
    local_hidden = []
    try:
        for path in paths:
            for layer in path:
                for owner, prop in ((layer, 'exclude'), (layer, 'hide_viewport'),
                                    (layer.collection, 'hide_viewport')):
                    if getattr(owner, prop):
                        changes.append((owner, prop, True))
                        setattr(owner, prop, False)
        context.view_layer.update()
        for obj in objects:
            local_hidden.append((obj, obj.hide_get(view_layer=context.view_layer)))
            if obj.hide_viewport:
                changes.append((obj, 'hide_viewport', True))
                obj.hide_viewport = False
            obj.hide_set(False, view_layer=context.view_layer)
        context.view_layer.update()
        debug(f"[Minimap framing] Temporarily showing MLO hierarchy: {root.name}")
        yield
    finally:
        for obj, hidden in local_hidden:
            obj.hide_set(hidden, view_layer=context.view_layer)
        for owner, prop, value in reversed(changes):
            setattr(owner, prop, value)
        context.view_layer.update()
        debug(f"[Minimap framing] Restored MLO visibility: {root.name}")


def clip_polygon_z(vertices, plane_z, keep_above):
    """Clip a convex polygon to one horizontal half-space, including edge crossings."""
    if not vertices:
        return []
    result = []
    previous = vertices[-1]
    previous_inside = previous.z >= plane_z if keep_above else previous.z <= plane_z
    for current in vertices:
        inside = current.z >= plane_z if keep_above else current.z <= plane_z
        if inside != previous_inside:
            factor = (plane_z - previous.z) / (current.z - previous.z)
            result.append(previous.lerp(current, factor))
        if inside:
            result.append(current)
        previous, previous_inside = current, inside
    return result


def camera_vertical_range(camera):
    if camera.type != 'CAMERA' or camera.data.type != 'ORTHO':
        raise ValueError('an orthographic camera is required')
    up = camera.matrix_world.to_3x3().col[2]
    if up.length <= 1e-12 or up.normalized().z < 1.0 - 1e-8:
        raise ValueError('the camera must point vertically downward')
    camera_z = camera.matrix_world.translation.z
    near, far = camera.data.clip_start, camera.data.clip_end
    if not all(math.isfinite(v) for v in (camera_z, near, far)) or not 0 < near < far:
        raise ValueError('the camera clipping range is invalid')
    return camera_z - far, camera_z - near


def visible_geometry_bounds(context, camera, debug):
    """Bounds of all visible MLO meshes inside clipping, independent of camera X/Y/scale.

    This is a geometric slab test, not a screen-space occlusion test. No RoomID
    or material filter is applied: Stage 4 measures the actual MLO geometry.
    """
    lower, upper = camera_vertical_range(camera)
    name = context.scene.mlo_name.strip()
    root = context.scene.objects.get(name) if name else None
    if root is None:
        raise ValueError('MLO Name must identify an object in this scene')
    depsgraph = context.evaluated_depsgraph_get()
    minimum_x = minimum_y = math.inf
    maximum_x = maximum_y = -math.inf
    sources = []
    for obj in (root, *root.children_recursive):
        if (obj.type != 'MESH' or obj.name not in context.scene.objects
                or not obj.visible_get(view_layer=context.view_layer)):
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        count = 0
        try:
            if mesh is None:
                raise ValueError(f"mesh '{obj.name}' could not be evaluated")
            mesh.calc_loop_triangles()
            vertices = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
            for triangle in mesh.loop_triangles:
                polygon = [vertices[index] for index in triangle.vertices]
                if not all(math.isfinite(value) for vertex in polygon for value in vertex):
                    raise ValueError(f"mesh '{obj.name}' contains non-finite coordinates")
                polygon = clip_polygon_z(polygon, lower, True)
                polygon = clip_polygon_z(polygon, upper, False)
                if not polygon:
                    continue
                count += 1
                for vertex in polygon:
                    minimum_x, maximum_x = min(minimum_x, vertex.x), max(maximum_x, vertex.x)
                    minimum_y, maximum_y = min(minimum_y, vertex.y), max(maximum_y, vertex.y)
        finally:
            evaluated.to_mesh_clear()
        if count:
            sources.append((obj.name, count))
    if not sources:
        raise ValueError('no visible MLO geometry intersects the camera clipping range')
    bounds = (minimum_x, maximum_x, minimum_y, maximum_y)
    debug(f"[Minimap centering] Camera: {camera.name}; visible Z=[{lower:.4f}, {upper:.4f}]; "
          f"XY bounds={bounds}; meshes/triangles={sources}")
    return bounds


def center_camera(context, camera, debug, bounds=None):
    """Update only world X/Y, retaining world Z and all camera data settings."""
    if camera.constraints or camera.animation_data:
        raise ValueError('the camera has constraints or animation')
    if camera.parent is not None and camera.parent_type != 'OBJECT':
        raise ValueError('the camera uses unsupported parenting')
    if bounds is None:
        bounds = visible_geometry_bounds(context, camera, debug)
    minimum_x, maximum_x, minimum_y, maximum_y = bounds
    target = camera.matrix_world.translation.copy()
    target.x = (minimum_x + maximum_x) / 2
    target.y = (minimum_y + maximum_y) / 2
    debug_position = tuple(target)
    if camera.parent is not None:
        target = (camera.parent.matrix_world @ camera.matrix_parent_inverse).inverted() @ target
    camera.location = target - camera.delta_location
    debug(f"[Minimap centering] Camera: {camera.name}; world position={debug_position}")


def fit_camera(context, camera, debug, margin=1.0):
    """Center and size from the same clipped geometry, with a percentage margin."""
    old_location = camera.location.copy()
    old_scale = camera.data.ortho_scale
    try:
        with temporary_mlo_visibility(context, debug):
            if camera.data.animation_data:
                raise ValueError('the camera data has animation')
            if abs(camera.data.shift_x) > 1e-6 or abs(camera.data.shift_y) > 1e-6:
                raise ValueError('Camera Shift must be zero')
            # Minimap export requires the standard unrotated top-down camera.
            basis = camera.matrix_world.to_3x3().normalized()
            if basis.col[0].x < 1 - 1e-8 or basis.col[1].y < 1 - 1e-8:
                raise ValueError('the minimap camera must have its original world orientation')
            bounds = visible_geometry_bounds(context, camera, debug)
            width, height = bounds[1] - bounds[0], bounds[3] - bounds[2]
            # Blender's frame accounts for sensor_fit, render aspect and pixel
            # aspect. Divide by the current scale; no iterative trial rendering.
            frame = camera.data.view_frame(scene=context.scene)
            unit_width = (max(v.x for v in frame) - min(v.x for v in frame)) / old_scale
            unit_height = (max(v.y for v in frame) - min(v.y for v in frame)) / old_scale
            if unit_width <= 0 or unit_height <= 0:
                raise ValueError('the camera frame has invalid dimensions')
            calculated = max(width / unit_width, height / unit_height)
            scale = calculated * (1 + margin / 100)
            prop = camera.data.bl_rna.properties['ortho_scale']
            if not math.isfinite(scale) or not prop.hard_min <= scale <= prop.hard_max:
                raise ValueError('the calculated orthographic scale is outside camera limits')
            center_camera(context, camera, debug, bounds=bounds)
            camera.data.ortho_scale = scale
            debug(f"[Minimap scale] Camera: {camera.name}; width={width:.4f}, height={height:.4f}, "
                  f"frame aspect={unit_width / unit_height:.6f}, calculated={calculated:.4f}, "
                  f"orthographic_scale={scale:.4f} ({margin:g}% margin)")
    except Exception:
        camera.location = old_location
        camera.data.ortho_scale = old_scale
        raise
