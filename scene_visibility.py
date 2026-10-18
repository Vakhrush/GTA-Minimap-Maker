"""Optional final Refresh visibility actions for Sollumz 2.9 scenes."""

import bpy


def hide_portal_entities(context, debug):
    name = context.scene.mlo_name.strip()
    matches = [a for ytyp in getattr(context.scene, 'ytyps', ()) for a in ytyp.archetypes
               if a.type == 'sollumz_archetype_mlo' and a.name == name]
    if len(matches) != 1:
        return ['Doors were not hidden: a unique MLO archetype matching MLO Name is required.']
    archetype = matches[0]
    portal_ids = {str(portal.id) for portal in archetype.portals if portal.id >= 0}
    hidden = set()
    warnings = []
    for entity in archetype.entities:
        # Sollumz stores the enum number as the portal ID (not an index).
        # Reading the RNA enum invokes an owner/cache lookup that can update YTYP.
        # Read its saved IDProperty directly, without invoking that callback.
        portal_id = str(entity.get('attached_portal_id', -1))
        if portal_id == '-1' or portal_id not in portal_ids:
            continue
        root = entity.linked_object
        if root is None:
            debug(f'[Minimap doors] Portal {portal_id}: no linked object')
            continue
        for obj in (root, *root.children_recursive):
            if obj.name in hidden or obj.name not in context.view_layer.objects:
                continue
            try:
                # Layer rendering changes hide_viewport; local hide_set survives
                # those temporary layer switches and also hides ordinary previews.
                obj.hide_set(True, view_layer=context.view_layer)
                hidden.add(obj.name)
            except RuntimeError as exc:
                warnings.append(f"Could not hide portal entity object '{obj.name}': {exc}")
    debug(f'[Minimap doors] Hidden objects: {sorted(hidden)}')
    return warnings


def hide_collisions(debug):
    try:
        operator = bpy.ops.sollumz.hide_collisions
        if not operator.poll():
            return 'Sollumz Hide Collisions is unavailable in the current context.'
        result = operator()
        if result != {'FINISHED'}:
            return 'Sollumz Hide Collisions did not finish successfully.'
        debug('[Minimap] Sollumz Hide Collisions completed')
    except Exception as exc:
        return f'Sollumz Hide Collisions could not run: {exc}'
    return None
