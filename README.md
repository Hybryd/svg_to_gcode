# svg_to_gcode
1. Open Inkscape and create a shape
2. Transform your object into paths
3. The paths that will be cut must be colored in red. The rest will be engraved
4. Save the image as an SVG file
5. Run the main file to create the gcode
```
python3 main.py -i examples/disquette.svg -o examples/disquette.gcode
```