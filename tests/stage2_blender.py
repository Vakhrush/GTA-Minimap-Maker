"""Run in a separate Blender 5.2 process, without opening or saving a user scene.

blender --background --factory-startup --python-exit-code 1
        --python tests/stage2_blender.py -- <installed Sollumz 2.9 package directory>
"""

import importlib.util
import math
from pathlib import Path
import sys

import addon_utils
import bpy
from mathutils import Matrix

sys.dont_write_bytecode = True
root = Path(__file__).resolve().parents[1]
sollumz = Path(sys.argv[sys.argv.index('--') + 1])
sys.path.insert(0, str(sollumz.parent))
# Use already-installed dependencies without changing extension preferences.
dependencies = (sollumz.parent.parent / '.user' / sollumz.parent.name / sollumz.name
                / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages')
sys.path.insert(0, str(dependencies))
addon_utils.enable(sollumz.name, default_set=True)  # In-memory test preferences only; never saved.
assert hasattr(bpy.types.Scene, 'ytyps'), 'Sollumz Room properties did not register'

spec = importlib.util.spec_from_file_location('minimap_stage2_test', root / '__init__.py',
                                             submodule_search_locations=[str(root)])
addon = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = addon
spec.loader.exec_module(addon)
addon.register()
geometry = sys.modules[spec.name + '.floor_geometry']
scene = bpy.context.scene
scene.mlo_name = 'test_mlo'
ytyp = scene.ytyps.add()
scene.ytyp_index = 0
mlo = ytyp.archetypes.add()
mlo.type = 'sollumz_archetype_mlo'
mlo.name = scene.mlo_name
for index, (name, floor_id) in enumerate([
    ('limbo', 0), ('basement', -1), ('hall', 0), ('upper', 2), ('other_hall', 0), ('LiMbO', 2),
]):
    room = mlo.rooms.add()
    room.name, room.floor_id = name, floor_id
    room.id = 500 + index  # Deliberately different from the material RoomID.

vertices, faces, slots = [], [], []


def plane(z, room_id, subdivisions=10, size=10):
    for x in range(subdivisions):
        for y in range(subdivisions):
            step = size / subdivisions
            start = len(vertices)
            vertices.extend([(x * step, y * step, z), ((x + 1) * step, y * step, z),
                             ((x + 1) * step, (y + 1) * step, z), (x * step, (y + 1) * step, z)])
            indices = tuple(range(start, start + 4))
            faces.append(indices if room_id in (0, 5) or (x + y) % 2 else indices[::-1])
            slots.append(room_id)


for z, room_id in [(0, 1), (3, 1), (3.2, 2), (6.2, 4), (6.4, 3), (9.4, 3)]:
    plane(z, room_id)
plane(5, 2, subdivisions=1, size=0.4)  # Small horizontal detail.
plane(100, 0)  # Both index zero and named Limbo must be excluded.
plane(200, 5)
mesh = bpy.data.meshes.new('collision')
mesh.from_pydata(vertices, [], faces)
mesh.update()
obj = bpy.data.objects.new(scene.mlo_name, mesh)
scene.collection.objects.link(obj)
for room_id in range(6):
    material = bpy.data.materials.new(f'collision_room_{room_id}')
    material.sollum_type = 'sollumz_material_collision'
    material.collision_properties.room_id = room_id
    mesh.materials.append(material)
for polygon, slot in zip(mesh.polygons, slots):
    polygon.material_index = slot
obj.location = (10, -12, 20)
obj.scale = (2, 3, 1.5)
obj.rotation_euler.z = 0.3
obj.modifiers.new('Evaluate triangulation', 'TRIANGULATE')
bpy.context.view_layer.update()
diagnostics = []
bounds, warnings = geometry.detect_floor_bounds(bpy.context, [-1, 0, 2], diagnostics.append)
assert not warnings, warnings
for floor_id, expected in {-1: (20, 24.5), 0: (24.8, 29.3), 2: (29.6, 34.1)}.items():
    assert all(abs(a - b) < 1e-4 for a, b in zip(bounds[floor_id], expected)), bounds
assert len(mesh.polygons) == len(faces)  # Original geometry was not replaced.
assert diagnostics

# Exercise the actual Refresh operator, including Stage 1 sparse IDs.
assert bpy.ops.gtaminimap.prepare_scene() == {'FINISHED'}
assert [item[2] for item in addon.operator.active_floor_cameras(scene)] == [1, 3, 7]
for floor_id, (lower, upper) in bounds.items():
    camera = scene.objects[addon.operator.floor_camera_name(floor_id)]
    assert abs(camera.location.z - (upper - 0.1 * (upper - lower))) < 1e-4
camera = scene.objects['MinimapCam_3floor']
camera.location.x, camera.location.y = 17, -4
camera.data.clip_start, camera.data.clip_end, camera.data.ortho_scale = 0.2, 80, 123
camera.rotation_euler = (0.02, 0.03, 0.04)
original_rotation = tuple(camera.rotation_euler)
assert bpy.ops.gtaminimap.prepare_scene() == {'FINISHED'}
assert tuple(camera.location)[:2] == (17, -4)
assert tuple(camera.rotation_euler) == original_rotation
assert abs(camera.data.clip_start - 0.2) < 1e-6
assert camera.data.clip_end == 80 and camera.data.ortho_scale == 123

# RoomID validation must not silently borrow another room or floor.
mesh.materials[1].collision_properties.room_id = 99
bad_bounds, warnings = geometry.detect_floor_bounds(bpy.context, [-1, 0, 2], lambda _: None)
assert not bad_bounds and 'invalid RoomIDs' in warnings[0]
previous_z = camera.location.z
assert bpy.ops.gtaminimap.prepare_scene() == {'FINISHED'}
assert camera.location.z == previous_z
mesh.materials[1].collision_properties.room_id = 1

# A ceiling reclassified as Limbo remains available to the downward-face fallback.
for polygon in mesh.polygons:
    if polygon.material_index == 3 and polygon.center.z > 9:
        polygon.material_index = 0
mesh.update()
bpy.context.view_layer.update()
camera.location.z = 77
assert bpy.ops.gtaminimap.prepare_scene() == {'FINISHED'}
assert abs(camera.location.z - 33.65) < 1e-4
assert abs(scene.objects['MinimapCam_basement'].location.z - 24.05) < 1e-4

# A large vertical surface is not a structural elevation level.
vertical_mesh = bpy.data.meshes.new('vertical_collision')
vertical_mesh.from_pydata([(0, 0, 0), (0, 100, 0), (0, 100, 100), (0, 0, 100)], [], [(0, 1, 2, 3)])
vertical_mesh.materials.append(mesh.materials[2])
obj.data = vertical_mesh
bpy.context.view_layer.update()
result, warnings = geometry.detect_floor_bounds(bpy.context, [0], lambda _: None)
assert not result and warnings
obj.data = mesh
bpy.context.view_layer.update()


def sample(z, area=100):
    return (z, z, z, area)


for samples in ([], [sample(0)], [sample(0), sample(3), sample(6)], [sample(0), sample(0.2)]):
    result, warnings = geometry.choose_floor_bounds({0: samples}, lambda _: None)
    assert not result and warnings
result, warnings = geometry.choose_floor_bounds(
    {-1: [sample(0), sample(4)], 2: [sample(3), sample(6)]}, lambda _: None)
assert not result and warnings
assert len(geometry.cluster_levels([sample(0), sample(0.008), sample(0.016)])) == 2

# Regression using the user's actual logged elevations and aggregate areas.
logged = {
    0: [sample(-6.5, 97.1886), sample(-4.1623, 97.1886), sample(-4, 303.447)],
    1: [sample(0, 305.1305), sample(0.1, 0.8591), sample(1, 9.0667)],
    2: [sample(4, 298.9629), sample(4.15, 0.6631), sample(5, 12.6933)],
}
result, warnings = geometry.choose_floor_bounds(logged, lambda _: None)
assert result == {0: (-4, 0), 1: (0, 4), 2: (4, 8)}, (result, warnings)
assert any('secondary lower levels' in message for message in warnings)
assert any('FloorID 2: estimated floor height 4.0000' in message for message in warnings)


def ceiling(z, area=300, upward=False):
    return (z, z, z, area, 'excluded_mesh', 'limbo', upward)


# Confirmed downward geometry takes precedence over extrapolation. Small details,
# upward faces and planes below the top floor cannot supply its ceiling.
result, warnings = geometry.choose_floor_bounds(logged, lambda _: None,
    [ceiling(3), ceiling(5, area=2), ceiling(6, upward=True), ceiling(7.5), ceiling(9)])
assert result[2] == (4, 7.5)
assert not any('estimated floor height' in message for message in warnings)
result, warnings = geometry.choose_floor_bounds(logged, lambda _: None,
    [ceiling(5, area=2), ceiling(6, upward=True)])
assert result[2] == (4, 8) and any('estimated floor height' in message for message in warnings)
result, warnings = geometry.choose_floor_bounds({0: [sample(0)]}, lambda _: None, [ceiling(3)])
assert result == {0: (0, 3)} and not warnings
result, warnings = geometry.choose_floor_bounds({0: [sample(0)]}, lambda _: None)
assert not result and warnings
result, warnings = geometry.choose_floor_bounds(
    {0: [sample(0), sample(3)], 1: [sample(4), sample(9)], 2: [sample(10)]}, lambda _: None)
assert result[2] == (10, 14) and any('estimated floor height 4.0000' in message for message in warnings)
# An already confirmed top ceiling is never overridden by excluded geometry.
result, warnings = geometry.choose_floor_bounds(
    {0: [sample(0), sample(4)]}, lambda _: None, [ceiling(3)])
assert result == {0: (0, 4)} and not warnings
# A real upper boundary completes the top floor; the height is not hardcoded.
logged[2].append(sample(8.5, 300))
result, warnings = geometry.choose_floor_bounds(logged, lambda _: None)
assert result[2] == (4, 8.5)
result, warnings = geometry.choose_floor_bounds({-1: [sample(-7)], 2: [sample(-2)]}, lambda _: None)
assert result == {-1: (-7, -2), 2: (-2, 3)}
# Do not bridge an unresolved intermediate floor.
result, warnings = geometry.choose_floor_bounds({0: [sample(0)], 1: [], 2: [sample(8)]}, lambda _: None)
assert not result
# An own ceiling must not extend through the next floor, even if the latter
# has no ceiling and therefore cannot itself produce a camera interval.
result, warnings = geometry.choose_floor_bounds(
    {0: [sample(0), sample(5)], 1: [sample(4)]}, lambda _: None)
assert not result and any('overlapping' in message for message in warnings)

# Parent transforms and delta location must not change world X/Y or orientation.
parent = bpy.data.objects.new('camera_parent', None)
scene.collection.objects.link(parent)
parent.rotation_euler = (0.3, 0.2, 0.1)
parent.scale = (2, 3, 4)
camera.parent = parent
camera.matrix_parent_inverse = Matrix.Translation((3, 4, 5))
camera.delta_location = (0.2, 0.4, 0.6)
bpy.context.view_layer.update()
before = camera.matrix_world.copy()
geometry.set_camera_world_height(camera, 42)
bpy.context.view_layer.update()
after = camera.matrix_world
assert abs(after.translation.z - 42) < 1e-4
assert all(abs(before.translation[i] - after.translation[i]) < 1e-4 for i in (0, 1))
assert all(abs(before[i][j] - after[i][j]) < 1e-4 for i in range(3) for j in range(3))
camera.constraints.new('LIMIT_LOCATION')
try:
    geometry.set_camera_world_height(camera, 99)
except ValueError:
    pass
else:
    raise AssertionError('Constrained camera should not be positioned silently')

# A named container can hold separate floors/ceilings at arbitrary nesting depths.
obj.name = 'original_collision_child'
root_object = bpy.data.objects.new('test_mlo', None)
scene.collection.objects.link(root_object)
root_object.location = (10, 20, 30)
root_object.scale = (2, 3, 2)
root_object.rotation_euler.z = 0.4
nested = bpy.data.objects.new('nested_collision_container', None)
scene.collection.objects.link(nested)
nested.parent = root_object
nested.location.z = 1


def child_plane(name, parent_obj, local_z, material):
    child_mesh = bpy.data.meshes.new(name)
    child_mesh.from_pydata([(0, 0, 0), (4, 0, 0), (4, 4, 0), (0, 4, 0)], [], [(0, 1, 2, 3)])
    child_mesh.materials.append(material)
    child = bpy.data.objects.new(name, child_mesh)
    scene.collection.objects.link(child)
    child.parent = parent_obj
    child.location.z = local_z
    return child


lower_child = child_plane('lower_collision', root_object, 0, mesh.materials[2])
upper_child = child_plane('upper_collision', nested, 2, mesh.materials[4])
upper_child.scale = (0.8, 0.9, 1)
visual_material = bpy.data.materials.new('visual_only')
child_plane('ignore_visual_mesh', nested, 1, visual_material)
child_plane('ignore_limbo_mesh', nested, 100, mesh.materials[0])
bpy.context.view_layer.update()
result, warnings = geometry.detect_floor_bounds(bpy.context, [0], lambda _: None)
assert not warnings and result == {0: (30.0, 36.0)}, (result, warnings)
assert bpy.ops.gtaminimap.prepare_scene() == {'FINISHED'}
assert abs(scene.objects['MinimapCam_1floor'].location.z - 35.4) < 1e-4

# A mesh root is analyzed together with its children (not only its descendants).
root_object.name = 'container_with_children'
lower_child.name = 'test_mlo'
upper_child.parent = lower_child
upper_child.location.z = 3
bpy.context.view_layer.update()
result, warnings = geometry.detect_floor_bounds(bpy.context, [0], lambda _: None)
assert not warnings and result == {0: (30.0, 36.0)}, (result, warnings)

# A real downward-facing Limbo mesh supplies the ceiling only as a fallback.
upper_child.data.materials[0] = mesh.materials[0]
upper_child.data.polygons[0].flip()
upper_child.data.update()
bpy.context.view_layer.update()
result, warnings = geometry.detect_floor_bounds(bpy.context, [0], lambda _: None)
assert not warnings and result == {0: (30.0, 36.0)}, (result, warnings)
upper_child.data.polygons[0].flip()
upper_child.data.update()

# Report missing usable geometry only after inspecting the hierarchy.
lower_child.name = 'lower_collision'
root_object.name = 'test_mlo'
lower_child.data.materials[0] = visual_material
upper_child.data.materials[0] = visual_material
bpy.context.view_layer.update()
result, warnings = geometry.detect_floor_bounds(bpy.context, [0], lambda _: None)
assert not result and 'no usable horizontal collision surfaces' in warnings[0]

scene.mlo_name = 'missing_mesh'
assert geometry.detect_floor_bounds(bpy.context, [0], lambda _: None)[1]
addon.unregister()
print('STAGE2_TESTS_PASSED: real Sollumz Rooms/materials, dense geometry, sparse IDs, world transforms, '
      'Limbo exclusion, ambiguity/fallback, Refresh, unchanged unrelated camera settings, nested MLO meshes')
