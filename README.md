# GTA Minimap Maker

Blender addon for generating GTA V MLO minimaps directly from Sollumz scenes.

The addon automatically renders an orthographic top view, converts it into vector graphics using Potrace, imports the vector into a GFX template using JPEXS Free Flash Decompiler and exports a ready-to-use minimap for GTA V.

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
- Sollumz 2.8.3+ (recommended)
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

### Shot Resolution

Higher values produce more detailed minimaps but increase export time.

Recommended values:

- 1024
- 2048

---

## Workflow

### 1. Refresh Minimap Mode

Click:

**Refresh Minimap Mode**

Switch the viewport to **Solid** shading.

The addon automatically creates **MinimapCam**.

---

### 2. Configure Camera

Adjust only:

**Object → Transform**

- Location Z

and

**Camera Data**

- Orthographic Scale

Do not modify:

- Camera RotationXYZ and LocationXY
- Camera Shift

---

### 3. Prepare the Scene

Configure the minimap appearance.

Examples:

- Hide unnecessary props.
- Paint objects using **Custom Paint**.
- Create white helper meshes to represent entrances, exits or other map icons (only one custom color).
- Prepare the scene exactly as you want it to appear on the minimap.

---

### 4. Enter MLO Name

Type the MLO name in the addon panel.

The addon automatically calculates the JOAAT hash and names the exported GFX accordingly.

---

### 5. Export

Click:

**Make Shot**

The addon automatically:

- renders the scene;
- generates vector layers;
- merges SVG layers;
- builds the final SVG;
- creates a GFX template;
- patches the MLO name;
- patches the JOAAT hash;
- imports the SVG into the GFX;
- exports the finished minimap.

---

## Output

The output directory contains:

- `int<hash>.gfx`
- `1.svg`
- minimap preview PNG

Temporary files are automatically removed.

---

## Current Limitations

- Designed for single-floor interiors.
- Camera Shift is not supported.
- Camera Rotation/LocationXY must remain unchanged.

---

## Roadmap

- Multi-floor minimap support
- Adding a GIF demo to the README file
- Additional options

---

## Support

If GTA Minimap Maker has been useful for your projects and saved you time, you can support its future development.

➡️ See DONATE.md