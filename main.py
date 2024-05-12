import argparse
from svg_to_gcode.svg_parser import parse_file_custom
from svg_to_gcode.compiler import Compiler, interfaces

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input',  dest="input_file", required=True)
parser.add_argument('-o', '--output',  dest="output_file", required=True)
args = parser.parse_args()

if args.input_file and args.output_file:

    gcode_compiler = Compiler(
        interface_class=interfaces.Gcode,
        movement_speed=1000,
        cutting_speed=500,
        cutting_power=1.0,
        drawing_speed=900,
        drawing_power=0.45,
        initial_z=0.0,
        drawing_z=7.0,
        cutting_z=5.0,
        cutting_passes=2,
        pass_depth=0
    )
    curves, areas = parse_file_custom(args.input_file)
    gcode_compiler.append_curves(curves)
    #gcode_compiler.append_areas(areas)
    gcode_compiler.compile_to_file(args.output_file)