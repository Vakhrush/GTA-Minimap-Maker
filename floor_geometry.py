"""Read-only collision analysis for automatic minimap camera heights.

Room IDs on collision materials are zero-based indices into archetype.rooms,
not RoomProperties.id. All measurements below are in world space.
"""

import math
from statistics import median


# Conservative tolerances, in Blender world units (areas in squared units).
HORIZONTAL_COS = math.cos(math.radians(5.0))
LEVEL_TOLERANCE = 0.01
DOMINANT_AREA_RATIO = 2.0
MIN_LEVEL_AREA = 0.25
MIN_RELATIVE_AREA = 0.20
MIN_FLOOR_HEIGHT = 0.50


def cluster_levels(samples):
    """Aggregate (min_z, max_z, mean_z, projected_area) without chain merging."""
    levels = []
    for sample in sorted(samples, key=lambda item: item[:4]):
        low, high, z, area = sample[:4]
        if not levels or max(levels[-1]['max_z'], high) - levels[-1]['min_z'] > LEVEL_TOLERANCE:
            levels.append({'min_z': low, 'max_z': high, 'weighted_z': z * area, 'area': area,
                           'sources': set(), 'up_area': 0.0, 'down_area': 0.0})
        else:
            level = levels[-1]
            level['max_z'] = max(level['max_z'], high)
            level['weighted_z'] += z * area
            level['area'] += area
        level = levels[-1]
        if len(sample) > 4:
            mesh_name, room_name, upward = sample[4:]
            level['sources'].add((mesh_name, room_name))
            level['up_area' if upward else 'down_area'] += area
    for level in levels:
        level['z'] = level['weighted_z'] / level['area']
    return levels


def choose_floor_bounds(samples_by_floor, debug, ceiling_samples=()):
    """Return reliable floor intervals and reasons for leaving other cameras alone."""
    bounds = {}
    warnings = []
    floors = {}
    ceilings = {}
    floor_areas = {}
    missing_upper = set()
    for floor_id, samples in sorted(samples_by_floor.items()):
        # Horizontal coplanarity: every vertex must lie within the same 0.01
        # world-unit Z band. Accumulate all polygons, not just a large seed face.
        levels = cluster_levels(samples)
        for level in levels:
            debug(f"[Minimap heights] FloorID {floor_id}: coplanar Z={level['z']:.4f}, "
                  f"area={level['area']:.4f}, up={level['up_area']:.4f}, down={level['down_area']:.4f}, "
                  f"mesh/room sources={sorted(level['sources'])}")
        threshold = max(MIN_LEVEL_AREA, max((v['area'] for v in levels), default=0) * MIN_RELATIVE_AREA)
        significant = [v for v in levels if v['area'] >= threshold]
        debug(f"[Minimap heights] FloorID {floor_id}: minimum level area={threshold:.4f}; "
              f"significant levels={len(significant)}")
        if not significant:
            warnings.append(f"FloorID {floor_id}: no reliable horizontal floor level. Camera height unchanged.")
            continue
        if len(significant) <= 2:
            # Preserve the established floor/ceiling interpretation for a pair.
            floor = significant[0]
            ceiling = significant[1] if len(significant) == 2 else None
        else:
            ranked = sorted(significant, key=lambda v: v['area'], reverse=True)
            if ranked[0]['area'] < DOMINANT_AREA_RATIO * ranked[1]['area']:
                warnings.append(f"FloorID {floor_id}: multiple competing horizontal levels. Camera height unchanged.")
                continue
            floor = ranked[0]
            above = [v for v in significant if v['min_z'] > floor['max_z']]
            if len(above) > 1:
                warnings.append(f"FloorID {floor_id}: upper boundary is ambiguous. Camera height unchanged.")
                continue
            ceiling = above[0] if above else None
            secondary = [round(v['z'], 4) for v in significant if v['max_z'] < floor['min_z']]
            if secondary:
                debug(f"[Minimap heights] FloorID {floor_id}: using dominant floor Z={floor['z']:.4f}; "
                      f"secondary lower levels {secondary} were not used for camera height.")
        floors[floor_id] = floor['max_z']
        floor_areas[floor_id] = floor['area']
        if ceiling is not None:
            ceilings[floor_id] = ceiling['min_z']
        debug(f"[Minimap heights] FloorID {floor_id}: selected main floor Z={floors[floor_id]:.4f}")

    ordered_ids = sorted(samples_by_floor)
    for index, floor_id in enumerate(ordered_ids):
        if floor_id not in floors:
            continue
        lower = floors[floor_id]
        upper = ceilings.get(floor_id)
        source = 'own horizontal ceiling'
        if upper is None and index + 1 < len(ordered_ids):
            next_id = ordered_ids[index + 1]
            upper = floors.get(next_id)
            source = f'next FloorID {next_id} main floor'
        if upper is None:
            missing_upper.add(floor_id)
            continue
        if upper - lower < MIN_FLOOR_HEIGHT:
            warnings.append(f"FloorID {floor_id}: elevation levels are too close or reversed. Camera height unchanged.")
            continue
        bounds[floor_id] = (lower, upper)
        debug(f"[Minimap heights] FloorID {floor_id}: lower={lower:.4f}, upper={upper:.4f}; source={source}")

    # Floor IDs need not be consecutive, but their vertical order must agree.
    invalid = set()
    for lower_id, upper_id in zip(ordered_ids, ordered_ids[1:]):
        if lower_id not in floors or upper_id not in floors:
            continue
        if (floors[lower_id] >= floors[upper_id] - LEVEL_TOLERANCE
                or (lower_id in bounds and bounds[lower_id][1] > floors[upper_id] + LEVEL_TOLERANCE)):
            invalid.update((lower_id, upper_id))
            warnings.append(
                f"FloorIDs {lower_id} and {upper_id}: overlapping or reversed elevation ranges. "
                "Camera heights unchanged."
            )
    for floor_id in invalid:
        bounds.pop(floor_id, None)

    # Only the last requested floor can extend beyond all known floors. Never
    # bridge an unresolved interior floor or replace an ambiguous main floor.
    last_id = ordered_ids[-1] if ordered_ids else None
    if last_id in missing_upper and last_id not in invalid:
        lower = floors[last_id]
        candidates = cluster_levels([
            sample for sample in ceiling_samples
            if len(sample) > 4 and not sample[6] and sample[0] - lower >= MIN_FLOOR_HEIGHT
        ])
        threshold = max(MIN_LEVEL_AREA, floor_areas[last_id] * MIN_RELATIVE_AREA)
        for level in candidates:
            debug(f"[Minimap heights] Excluded ceiling candidate: Z={level['z']:.4f}, "
                  f"down area={level['down_area']:.4f}, required area={threshold:.4f}, "
                  f"sources={sorted(level['sources'])}")
        reliable = [level for level in candidates if level['down_area'] >= threshold]
        if reliable:
            # The nearest sufficiently large downward plane is the first ceiling
            # above the floor; a higher roof should not supersede it.
            upper = reliable[0]['min_z']
            bounds[last_id] = (lower, upper)
            missing_upper.remove(last_id)
            debug(f"[Minimap heights] FloorID {last_id}: lower={lower:.4f}, upper={upper:.4f}; "
                  "source=excluded downward-facing ceiling")
        else:
            previous = [(floor_id, upper - low) for floor_id, (low, upper) in sorted(bounds.items())
                        if floor_id < last_id]
            if previous:
                height = median(value for _, value in previous)
                upper = lower + height
                bounds[last_id] = (lower, upper)
                missing_upper.remove(last_id)
                warnings.append(f"FloorID {last_id}: estimated floor height {height:.4f} from previous floors; "
                                f"estimated upper Z={upper:.4f}, camera Z={upper - 0.1 * height:.4f}.")
                debug(f"[Minimap heights] FloorID {last_id}: previous heights={previous}; "
                      f"source=estimated median height; lower={lower:.4f}, upper={upper:.4f}")
    for floor_id in sorted(missing_upper - invalid):
        warnings.append(f"FloorID {floor_id}: no confirmed upper boundary or usable previous height. Camera height unchanged.")
    return bounds, warnings


def detect_floor_bounds(context, floor_ids, debug):
    """Inspect the named MLO hierarchy without changing geometry, materials or Rooms."""
    scene = context.scene
    name = scene.mlo_name.strip()
    root = scene.objects.get(name) if name else None
    if root is None:
        return {}, ["Camera heights unchanged: MLO Name must identify an object in this scene."]
    objects = [obj for obj in (root, *root.children_recursive)
               if obj.type == 'MESH' and obj.name in scene.objects]
    if not objects:
        return {}, ["Camera heights unchanged: no mesh objects found in the MLO hierarchy."]
    matches = [a for ytyp in getattr(scene, 'ytyps', ()) for a in ytyp.archetypes
               if a.type == 'sollumz_archetype_mlo' and a.name == name]
    if len(matches) != 1:
        return {}, ["Camera heights unchanged: a unique MLO archetype matching MLO Name is required."]
    rooms = list(matches[0].rooms)
    samples = {floor_id: [] for floor_id in floor_ids}
    ceiling_samples = []
    invalid_room_ids = set()
    depsgraph = context.evaluated_depsgraph_get()
    debug(f"[Minimap heights] MLO root: {root.name}; meshes: {[obj.name for obj in objects]}")
    for obj in objects:
        counts = dict(horizontal=0, non_horizontal=0, limbo=0, non_collision=0)
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            if mesh is None:
                return {}, [f"Camera heights unchanged: MLO child mesh '{obj.name}' could not be evaluated."]
            mesh.calc_loop_triangles()
            matrix = evaluated.matrix_world
            vertices = [matrix @ v.co for v in mesh.vertices]
            # Object material slots also account for OBJECT-linked material overrides.
            # Read RoomID from original datablocks: custom material properties may
            # change without rebuilding the dependency graph's evaluated material.
            materials = [slot.material.original if slot.material else None for slot in evaluated.material_slots]
            for triangle in mesh.loop_triangles:
                a, b, c = (vertices[i] for i in triangle.vertices)
                cross = (b - a).cross(c - a)
                length = cross.length
                low, high = min(a.z, b.z, c.z), max(a.z, b.z, c.z)
                if (length <= 1e-12 or abs(cross.z) / length < HORIZONTAL_COS
                        or high - low > LEVEL_TOLERANCE):
                    counts['non_horizontal'] += 1
                    continue
                material = materials[triangle.material_index] if triangle.material_index < len(materials) else None
                # Keep downward horizontal faces for the last-floor fallback,
                # including surfaces excluded from normal Room/FloorID grouping.
                if cross.z < 0:
                    label = 'non-collision material'
                    if material is not None and getattr(material, 'sollum_type', None) == 'sollumz_material_collision':
                        index = material.collision_properties.room_id
                        label = rooms[index].name if 0 <= index < len(rooms) else f'invalid RoomID {index}'
                    ceiling_samples.append((low, high, (a.z + b.z + c.z) / 3, abs(cross.z) / 2,
                                            obj.name, label, False))
                if material is None or getattr(material, 'sollum_type', None) != 'sollumz_material_collision':
                    counts['non_collision'] += 1
                    continue
                room_id = material.collision_properties.room_id
                if room_id == 0:
                    counts['limbo'] += 1
                    continue
                if not 0 <= room_id < len(rooms):
                    invalid_room_ids.add(room_id)
                    continue
                room = rooms[room_id]
                if room.name.strip().casefold() == 'limbo':
                    counts['limbo'] += 1
                    continue
                if room.floor_id in samples:
                    samples[room.floor_id].append((low, high, (a.z + b.z + c.z) / 3, abs(cross.z) / 2,
                                                   obj.name, room.name, cross.z > 0))
                    counts['horizontal'] += 1
            debug(f"[Minimap heights] Mesh: {obj.name}; triangle counts: {counts}")
        finally:
            evaluated.to_mesh_clear()
    if invalid_room_ids:
        return {}, [f"Camera heights unchanged: collision materials reference invalid RoomIDs {sorted(invalid_room_ids)}."]
    if not any(samples.values()):
        return {}, ["Camera heights unchanged: no usable horizontal collision surfaces found in the MLO hierarchy (excluding RoomID 0 / Limbo)."]
    return choose_floor_bounds(samples, debug, ceiling_samples)


def set_camera_world_height(camera, height):
    """Translate only along world Z, preserving rotation, scale and world X/Y."""
    # Constraints/drivers may override the requested position; do not claim success.
    if camera.constraints or camera.animation_data:
        raise ValueError("the camera has constraints or animation")
    target = camera.matrix_world.translation.copy()
    target.z = height
    if camera.parent is not None:
        if camera.parent_type != 'OBJECT':
            raise ValueError("the camera uses unsupported parenting")
        parent_matrix = camera.parent.matrix_world @ camera.matrix_parent_inverse
        target = parent_matrix.inverted() @ target
    camera.location = target - camera.delta_location


def set_camera_clipping(camera, lower, upper, debug):
    """Clip from the actual camera position to 1% of a floor height below its floor.

    Blender's orthographic camera looks along local -Z; clip distances start at
    the camera, not at UpperZ. Thus 1.01*FloorHeight must lose the camera's
    setback from UpperZ (0.10*FloorHeight after automatic height placement).
    The caller updates the dependency graph before reading matrix_world here.
    """
    if camera.data.type != 'ORTHO':
        raise ValueError('an orthographic camera is required')
    if camera.constraints or camera.animation_data or camera.data.animation_data:
        raise ValueError('the camera has constraints or animation')
    up = camera.matrix_world.to_3x3().col[2]
    if up.length <= 1e-12 or (up.normalized().z < 1.0 - 1e-8):
        raise ValueError('the camera must point vertically downward')
    height = upper - lower
    camera_z = camera.matrix_world.translation.z
    if not all(math.isfinite(v) for v in (lower, upper, camera_z)) or not lower < camera_z < upper:
        raise ValueError('the camera must be between the detected floor boundaries')
    clip_end = height * 1.01 - (upper - camera_z)
    clip_start = max(0.001, camera.data.bl_rna.properties['clip_start'].hard_min)
    if (clip_end <= clip_start or camera_z - lower <= clip_start
            or clip_end > camera.data.bl_rna.properties['clip_end'].hard_max):
        raise ValueError('the calculated clipping range is outside camera limits')
    camera.data.clip_start = clip_start
    camera.data.clip_end = clip_end
    debug(f"[Minimap clipping] Camera: {camera.name}; floor height={height:.4f}, camera Z={camera_z:.4f}, "
          f"clip_start={clip_start:.4f}, clip_end={clip_end:.4f}, "
          f"visible Z=[{camera_z - clip_end:.4f}, {camera_z - clip_start:.4f}]")
