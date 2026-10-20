# GTA Minimap Maker

Blender addon for generating GTA V MLO minimaps directly from Blender scenes with Sollumz.

The addon automatically renders an orthographic top view, converts it into vector graphics using Potrace, imports the vector into a GFX template using JPEXS Free Flash Decompiler and exports a ready-to-use minimap for GTA V.

---

## Video Tutorial

[Watch the GTA Minimap Maker tutorial on YouTube](https://www.youtube.com/watch?v=cxDXExwygJg)

---

## Features

- One-click minimap generation
- Automatic orthographic rendering
- Layered rendering (Background, Shell, Entity, Walls, Custom)
- Automatic SVG generation using Potrace
- Automatic GFX generation using JPEXS
- Automatic JOAAT hash generation
- Custom object painting (only one custom color)
- Ready-to-use GTA V minimap export

---

## Requirements

- Blender 5.1+ (earlier versions have not been tested)
- Sollumz 2.9.0+ (recommended)
- JPEXS Free Flash Decompiler

### JPEXS Free Flash Decompiler

https://github.com/jindrapetrik/jpexs-decompiler

### Potrace (included)

https://potrace.sourceforge.net/

### Works better with GTA Scene Rebuilder

https://github.com/Vakhrush/GTA-Scene-Rebuilder

---

## Installation

1. Download the latest release.
2. Open Blender.
3. **Edit → Preferences → Add-ons**
4. Click **Install...**
5. Select the ZIP archive.
6. Enable **GTA Minimap Maker**.

---

## Addon Settings

Open:

**Edit → Preferences → Add-ons → GTA Minimap Maker**

Configure the following options:

### Output Path

Directory where generated minimaps will be saved.

### JPEXS Folder

Folder containing **ffdec-cli.exe**.

Example:

```text
C:\Program Files (x86)\FFDec\
```

### Map Quality

Choose the resolution used to render each floor before vector conversion:

| Preset | Resolution |
| --- | --- |
| Low | 1024 × 1024 |
| Medium (default) | 2048 × 2048 |
| High | 4096 × 4096 |
| Ultra | 8192 × 8192 |

Higher values capture more detail but increase processing time. Enable **Manual** to enter a custom resolution in **Manual Quality** (minimum 1024). Manual mode is disabled by default.

### Author

Optional author name written into the exported GFX metadata.

### Minimap Colors

Configure **Entity Color**, **Shell Color**, and **Walls**. The Walls color is also used for automatic shell outlines and the solid background when enabled.

The same colors are available in the **GTA Tools → GTA Minimap Maker** panel, together with **Reset Minimap Colors**.

### Custom Paint

Choose **Custom Paint Color**, select mesh objects, and click **Apply Color To Selected Meshes** in the addon panel. This sets their object color for scene preparation. The current export converts the custom layer to a single white vector layer; it does not preserve multiple custom colors.

### Background

Expand the section and choose one of two mutually exclusive modes:

- **Automatically Create Walls from Shell** (default): adds an outward outline around the Shell geometry, filled with the Walls color. The outline is exported as filled vector geometry, not an SVG stroke. **Wall Thickness** controls its width and is available only in this mode.
- **Fill Background**: includes a solid background layer using the Walls color.

### Advanced Settings

These settings are applied when you click **Refresh Minimap Mode**:

| Setting | Default | Purpose |
| --- | --- | --- |
| Orthographic Scale Margin | 1% | Adds space around the geometry fitted into each camera. |
| Camera Clipping Margin | 1% | Adds a margin based on the detected floor height, accounting for the camera's actual Z position. |
| Camera Height Offset | 10% | Places the camera this percentage of the floor height below its upper boundary. |

### Automatically Hide Collisions

Enabled by default. Runs Sollumz **Hide Collisions** as the final scene operation of Refresh, after the cameras have been configured. If the operator is unavailable, the addon reports a warning.

### Hide doors

Enabled by default. Hides objects linked to MLO entities with a valid portal assignment, including their children. This uses portal assignments rather than object names, so it applies to all matching portal-linked entities. It does not delete objects or change YTYP assignments.

### Keep Source SVG Files

Enabled by default. Keeps the numbered floor SVG files alongside the GFX. Disable it to remove the current export's floor SVG files after a successful GFX build. If the GFX build fails, the source SVG files are retained.

### Debug Info

Enable it to print detailed diagnostics and external tool output to the console, including FloorIDs, camera setup, used and unused cameras, and export steps. Warnings and status notifications can still appear when debug output is disabled.

---

## Workflow

### 1. Refresh Minimap Mode

Click **Refresh Minimap Mode** and use **Solid** viewport shading.

The addon:
- refresh attempts to use the selected MLO archetype, or the only MLO available. If automatic detection is unsuccessful, enter the name manually and refresh again.
- reads the FloorID values of all Rooms in the relevant MLO;
- sorts the unique FloorIDs and creates one minimap camera per detected floor;
- detects approximate floor heights from collision geometry and RoomID assignments;
- configures each camera's height, clipping, horizontal center, and orthographic scale independently;
- applies the optional door and collision hiding settings.

If MLO or Room data is unavailable, Refresh reports the reason and uses one default floor. Camera parameters that cannot be calculated remain unchanged; inspect the warnings before exporting.

---

### 2. Review Cameras and Prepare the Scene

Check the Camera View for every detected floor. Automatic height detection is approximate. For the highest floor, the addon can use a downward-facing ceiling surface or estimate the height from previously detected floors, with a warning when an estimate is used.

If needed, adjust camera position, **Orthographic Scale**, **Clip Start**, and **Clip End** manually. Running Refresh again recalculates the supported camera settings.
For multi-floor interiors, adjust the cameras' Clip Start / Clip End settings if necessary to prevent lower floors from appearing in the camera view. If unwanted details appear in the final .svg file, it means the camera has captured geometry from the floor below, and you need to reduce the Clip End distance.

Keep the original downward-facing camera orientation and zero **Camera Shift**.

Prepare the visible geometry and colors:

- Hide unnecessary props.
- Adjust Entity, Shell, and Walls colors.
- Use **Custom Paint** for helper meshes such as entrances, exits, or map icons. Only one custom color is supported, and it must be different from the other Minimap Colors.
- Review the Background mode and Wall Thickness in addon preferences.

---

### 3. Export

Click **Create GFX**.

For each active floor, the addon renders temporary layers, converts them to SVG with Potrace, and merges them into a numbered floor SVG. It then uses JPEXS to import the floor shapes into the GFX template and configure the MLO name, hash, scale, and placement.

Only cameras corresponding to the current detected FloorIDs are used. Older unused minimap cameras are not exported.

---

## Output

Files are written into a `Minimap_<blend filename>` subfolder of **Output Path** (`Minimap_Untitled` for an unsaved scene).

The output contains:

- `int<hash>.gfx` — the finished minimap;
- numbered floor SVG files when **Keep Source SVG Files** is enabled.

SVG filenames follow the FloorID, including when some FloorIDs are absent:

| FloorID | SVG filename |
| --- | --- |
| -1 (basement) | `1.svg` |
| 0 | `3.svg` |
| 1 | `5.svg` |
| 2 | `7.svg` |
| 3 | `9.svg` |

Without a basement, `1.svg` is used temporarily for template import and removed afterward. PNG previews are no longer generated; temporary raster layers are removed after processing. With **Keep Source SVG Files** disabled, a successful export into a clean output folder leaves only the GFX file.

For more detailed information about the add-on, read [How it works](How_it_works.md) or [Как это работает](How_it_works_RU.md).

---

## Support

If GTA Minimap Maker has been useful for your projects and saved you time, you can support its future development.

➡️ See [DONATE.md](DONATE.md)
