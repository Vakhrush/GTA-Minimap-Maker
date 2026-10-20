# How the addon works

The addon uses `portrace.exe` to vectorize preconfigured viewport captures, and JPEXS to edit and create `.gfx` files.

I created the `.gfx` template based on a multi-floor interior. In the template, the values that need to be changed and the sprite bounds have been adjusted to make it as versatile as possible.

This addon applies the sprite's scale and position over the template bounds. Everything works correctly in all the newly created interiors I have tested. Incorrect minimap scale or positioning is more likely to be an exception with certain interiors.

When you first use the addon, specify the path to JPEXS and the output path for `.gfx` files in the settings. If the output path is empty, the `.gfx` will be saved in the project folder.

In the addon panel, click **Refresh minimap**. The addon will automatically do the following:

- Switch the view to shade, recolor all entities to the prop color used on vanilla GTA minimaps, change the viewport background to the wall or background color used on GTA minimaps, and try to find the shell through Sollumz and color it as well. Cavity and shadows will be disabled, and the lighting will switch to flat to match GTA minimaps as closely as possible.
- Hide collisions through Sollumz and hide doors (all props attached to portals). You can disable this in the addon settings if you prefer.
- Find the MLO and fill in **MLO name** automatically. If this does not happen, enter it manually and click **Refresh minimap** again.
- Analyze the Rooms in the YTYP in Sollumz and count the floors.
- Create cameras according to the number of floors and position them at the appropriate floor heights. Height calculation uses the detected MLO: collision materials attached to Rooms (and Rooms are, of course, associated with floors) are used to identify surfaces and calculate the distance between them. An average is used if the interior has changes in elevation. If the height of a floor cannot be calculated, the height of already known floors is used as a last resort.
- Use the floor heights to set the cameras' **Clip Start / Clip End** with a small margin, which you can adjust in the addon settings if needed. Clip Start / End is necessary to prevent the cameras from capturing lower floors when saving the `.gfx`.
- Automatically center each camera on the visible MLO geometry and adjust its **Orthographic Scale** to the MLO bounds with a small margin, which you can also adjust in the addon settings.

Then, when you click **Create .GFX**, the addon does the following:

- Captures the shell, entities, and props with `custom_color` separately, processing each floor in turn.
- Processes the captures with `portrace.exe` using the parameters I set (you can change these in `operator.py`; see `def run_potrace(pbm_path, svg_path)`). `Portrace.exe` produces black-and-white outlines in `.svg` format.
- Combines the resulting `.svg` files into a single `.svg`, coloring the internal layers with the specified colors.

The layers inside the `.svg` follow a set order with some conditions, but the general principle is: background first, then shell, entity, walls (optional), and custom color. The walls layer contains all objects painted in the walls color, as well as the shell outline converted to ordinary vector geometry if that background method is selected in the settings.

- Each `.svg` is given its corresponding name: `1`, `3`, `5`, `7`, `9`.
- JPEXS then exports the addon's prepared `intEXAMPLE.gfx` template to `.xml`.
- The addon hashes **MLO name** and inserts it into the corresponding `.xml` fields. In the JPEXS graphical interface, this is **frame 2 → FrameLabel** (`name: "INT*"`), where the asterisk stands for the hashed name. It is also inserted into **ExporterInfo** (`int*`). In **ExportAssets**, MLO name is inserted without hashing. The current modification date and an author/publisher entry are added to **Metadata** (you can change this entry in the addon settings).
- The child scale and transform of the sprites are adjusted in the `.xml` according to a formula, depending on the number of floors (see `operator.py`, line 176, or search for `TranslateX&TranslateY`). Sprite 1 is the basement (`floorId -1`), sprite 3 is floor zero (`floorId 0`), and so on up to sprite 9, which is the third floor (`floorId 3`). The parent **BOUNDS SCALE** in the template is `20480`. Each camera's orthographic scale is converted to internal units, as are its X and Y coordinates. This offsets the sprite relative to its pivot in its own units, just as your MLO interior is offset from the world origin in Blender.
- JPEXS builds the finished `intEXAMPLE.xml` into a `.swf`, and the `.swf` is renamed to `.gfx`.
- The generated `.svg` files are imported into `intEXAMPLE.gfx` without **UPDATE BOUNDS**.
- `intEXAMPLE.gfx` is renamed to `int***.gfx`, where the asterisks stand for the hashed MLO name.
- Temporary files are deleted from the same folder.

If needed, you can edit the source `.svg` files in any vector editor, such as Inkscape. The files edited in Inkscape can easily be imported manually through **JPEXS → Import shapes** by selecting the folder containing the `.svg` files.

**Important:** do not use **Import shapes → Update bounds** when importing.

## Preparing a minimap in Blender

You can adjust **Minimap Colors** in the addon panel in Blender.

In Blender itself, you can use primitives and simply hide unnecessary props to get the minimap quality you want.

I recommend saving the project before making changes to the scene.

Adjust **Clip Start / End** in the camera settings if outlines of props from lower floors are still visible.

If your MLO interior is very large and props look blurry (like blobs), try selecting Ultra quality in the addon settings or entering higher values manually. Keep in mind that the higher the value, the longer Blender will take to render and vectorize the layers.

For an example of creating a minimap with my addon, follow the link:

Enjoy!
