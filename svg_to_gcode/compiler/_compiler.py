from typing import List, Tuple, Type
import warnings

import tqdm

from svg_to_gcode.compiler.interfaces import Interface
from svg_to_gcode.geometry import Curve, Line, Vector
from svg_to_gcode.geometry import LineSegmentChain
from svg_to_gcode import UNITS, TOLERANCES
from shapely.geometry import Point, LineString, MultiLineString
from shapely.geometry.polygon import Polygon
import numpy as np

"""
TODO:
For closed path with fill set as a shade of gray, compute a polygon from a LineSegmentChain
and generate random points inside of it.
Consider its outer box and
follow https://stackoverflow.com/questions/36399381/whats-the-fastest-way-of-checking-if-a-point-is-inside-a-polygon-in-python
"""

class Compiler:
    """
    The Compiler class handles the process of drawing geometric objects using interface commands and assembling
    the resulting numerical control code.
    """

    def __init__(
        self,
        interface_class: Type[Interface],
        movement_speed,
        cutting_speed,
        drawing_speed,
        cutting_power=1.0,
        drawing_power=0.2,
        initial_z=0.0,
        drawing_z=7.0,
        cutting_z=5.0,
        cutting_passes=1,
        pass_depth=2,
        dwell_time=0,
        drawing_point_time=20,
        unit=None,
        custom_header=None,
        custom_footer=None
    ):
        """

        :param interface_class: Specify which interface to use. The most common is the gcode interface.
        :param movement_speed: the speed at which to move the tool when moving. (units are determined by the printer)
        :param cutting_speed: the speed at which to move the tool when cutting. (units are determined by the printer)
        :param drawing_speed: the speed at which to move the tool when drawing. (units are determined by the printer)
        :param initial_z: the initial z value,
        :param drawing_z: the z value for drawing,
        :param cutting_z: the z value for cutting,
        :param cutting_passes: the number of passes when cutting,
        :param pass_depth: AKA, the depth your laser cuts in a pass.
        :param dwell_time: the number of ms the tool should wait before moving to another cut. Useful for pen plotters
        :param drawing_point_time: the number of ms the laser has to wait to draw a point
        :param unit: specify a unit to the machine
        :param custom_header: A list of commands to be executed before all generated commands. Default is [laser_off,]
        :param custom_footer: A list of commands to be executed after all generated commands. Default is [laser_off,]
        """
        self.interface = interface_class()
        self.movement_speed = movement_speed
        self.cutting_speed = cutting_speed
        self.drawing_speed = drawing_speed
        self.cutting_power = cutting_power
        self.drawing_power = drawing_power
        self.initial_z = initial_z
        self.drawing_z = drawing_z
        self.cutting_z = cutting_z
        self.cutting_passes = cutting_passes
        self.pass_depth = abs(pass_depth)
        self.dwell_time = dwell_time
        self.drawing_point_time = drawing_point_time

        if self.cutting_passes*self.pass_depth > self.cutting_z:
            raise ValueError(f"Too many passes. The laser will collide the material.")

        if (unit is not None) and (unit not in UNITS):
            raise ValueError(f"Unknown unit {unit}. Please specify one of the following: {UNITS}")
        
        self.unit = unit

        if custom_header is None:
            custom_header = [self.interface.laser_off()]

        if custom_footer is None:
            custom_footer = [self.interface.laser_off()]

        self.header = [self.interface.set_absolute_coordinates(),
                       self.interface.set_movement_speed(self.movement_speed)] + custom_header
        self.footer = custom_footer
        self.body_cut = []
        self.body_draw = []


    def compile(self):
        """
        Assembles the code in the header, body and footer, saving it to a file.

        :param passes: the number of passes that should be made. Every pass the machine moves_down (z-axis) by
        self.pass_depth and self.body is repeated.
        :return returns the assembled code. self.header + [self.body, -self.pass_depth] * passes + self.footer
        """

        if (len(self.body_draw) + len(self.body_cut)) == 0:
            warnings.warn("Compile with an empty body (no curves). Is this intentional?")

        gcode = []

        gcode.extend(self.header)
        gcode.append(self.interface.set_unit(self.unit))

        self.interface.set_movement_speed(self.movement_speed)
        # Set z for drawing
        gcode.append(self.interface.linear_move(z=(self.drawing_z-self.initial_z)))

        if len(self.body_draw):
            # Add gcode for drawing first
            gcode.extend(["; Start drawing"])
            gcode.extend(self.body_draw)

        if len(self.body_cut) > 0:
            gcode.extend(["; Start cutting"])
            # Set z for cutting
            # gcode.append(self.interface.linear_move(z=(self.cutting_z-self.drawing_z)))
            gcode.append(self.interface.linear_move(z=self.cutting_z))

            # Add gcode for cutting
            for i in range(self.cutting_passes):
                gcode.extend([f"; Pass {i+1}/{self.cutting_passes}"])
                gcode.extend(self.body_cut)

                if i < self.cutting_passes - 1:  # If it isn't the last pass, turn off the laser and move down
                    gcode.append(self.interface.laser_off())

                    if self.pass_depth > 0:
                        gcode.append(self.interface.set_relative_coordinates())
                        gcode.append(self.interface.linear_move(z=-self.pass_depth))
                        gcode.append(self.interface.set_absolute_coordinates())

        gcode.extend(self.footer)

        gcode = filter(lambda command: len(command) > 0, gcode)

        return '\n'.join(gcode)

    def apply_offset(self):
        offset_x = 0
        offset_y = 0
         

    # def compile_to_file(self, file_name: str, passes=1):
    def compile_to_file(self, file_name: str):
        """
        A wrapper for the self.compile method. Assembles the code in the header, body and footer, saving it to a file.

        :param file_name: the path to save the file.
        :param passes: the number of passes that should be made. Every pass the machine moves_down (z-axis) by
        self.pass_depth and self.body is repeated.
        """
        print("Generating Gcode file...")

        with open(file_name, 'w') as file:
            # file.write(self.compile(passes=passes))
            file.write(self.compile())


    def append_polygon(
        self,
        polygon: Polygon,
        grey_value: int,
        fill_method: str = "diagonal"
    ):
        if polygon.is_empty:
            warnings.warn("Attempted to parse empty Polygon")
            return []
        
        # points = self.fill_with_points(polygon=polygon, grey_value=grey_value)
        lines = []
        if fill_method == "diagonal":
            lines = self.fill_with_lines(polygon=polygon, grey_value=grey_value, orientation=fill_method)
        
        if len(lines) == 0:
            return []
        # if len(points) == 0:
        #     # warnings.warn("Polygon has no point inside.")
        #     return []
        x, y = lines[0].xy  
        
        code = []

        # start = points[0].start
        start = Vector(x[0], y[0])#points[0]

        if self.interface.position is None or abs(self.interface.position - start) > TOLERANCES["operation"]:

            code = [
                self.interface.laser_off(),
                self.interface.set_movement_speed(self.movement_speed),
            ]
            if self.dwell_time > 0:
                code = [self.interface.dwell(self.dwell_time)] + code
        
        for line in lines:
            x, y = line.xy
            code.append(self.interface.linear_move(x[0], y[0]))
            code.append(self.interface.set_movement_speed(self.cutting_speed))
            code.append(self.interface.set_laser_power(self.cutting_power))
            code.append(self.interface.linear_move(x[1], y[1]))
            code.append(self.interface.laser_off())
            code.append(self.interface.set_movement_speed(self.movement_speed))
       
        self.body_draw.extend(code)

        # Don't dwell and turn off laser if the new start is at the current position
        # if self.interface.position is None or abs(self.interface.position - start) > TOLERANCES["operation"]:
        #     if self.dwell_time > 0:
        #         code = [self.interface.dwell(self.dwell_time)]

        #     code.extend([
        #         self.interface.laser_off(),
        #         self.interface.set_movement_speed(self.movement_speed),
        #         # self.interface.linear_move(start.x, start.y),
        #         # self.interface.set_movement_speed(self.drawing_speed),
        #     ])
            

        # for point in points:
        #     code.extend([
        #         self.interface.draw_point(
        #             point=point,
        #             drawing_power=self.drawing_power,
        #             drawing_point_time=self.drawing_point_time
        #         )
        #     ])
        
        # self.body_draw.extend(code)


    def append_line_chain(self, line_chain: LineSegmentChain, cut=False):
        """
        Draws a LineSegmentChain by calling interface.linear_move() for each segment. The resulting code is appended to
        self.body
        """

        if line_chain.chain_size() == 0:
            warnings.warn("Attempted to parse empty LineChain")
            return []

        code = []

        start = line_chain.get(0).start

        # Don't dwell and turn off laser if the new start is at the current position
        if self.interface.position is None or abs(self.interface.position - start) > TOLERANCES["operation"]:

            # code = [self.interface.laser_off(), self.interface.set_movement_speed(self.movement_speed),
            #         self.interface.linear_move(start.x, start.y), self.interface.set_movement_speed(self.cutting_speed),
            #         self.interface.set_laser_power(1)]
            if cut:
                code = [
                    self.interface.laser_off(),
                    self.interface.set_movement_speed(self.movement_speed),
                    self.interface.linear_move(start.x, start.y),
                    self.interface.set_movement_speed(self.cutting_speed),
                    self.interface.set_laser_power(self.cutting_power)
                ]
            else:
                code = [
                    self.interface.laser_off(),
                    self.interface.set_movement_speed(self.movement_speed),
                    self.interface.linear_move(start.x, start.y),
                    self.interface.set_movement_speed(self.drawing_speed),
                    self.interface.set_laser_power(self.drawing_power)
                ]

            if self.dwell_time > 0:
                code = [self.interface.dwell(self.dwell_time)] + code

        for line in line_chain:
            code.append(self.interface.linear_move(line.end.x, line.end.y))
        if cut:
            self.body_cut.extend(code)
        else:
            self.body_draw.extend(code)


    def append_curves(self, curves: List[Curve]):
        """
        Draws curves by approximating them as line segments and calling self.append_line_chain(). The resulting code is
        appended to self.body
        """
        print("Transforming Bezier curves to line segments...")
        for curve in tqdm.tqdm(curves):

            line_chain = LineSegmentChain()

            approximation = LineSegmentChain.line_segment_approximation(curve)

            line_chain.extend(approximation)

            self.append_line_chain(line_chain, curve.cut)
    

    def color_to_grey(self, color: str) -> int:
        """
        NTSC formula: 0.299 x Red + 0.587 x Green + 0.114 x Blue.
        https://stackoverflow.com/questions/29643352/converting-hex-to-rgb-value-in-python
        """
        color = color.lstrip("#")
        r,g,b = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        return int(0.299*r + 0.587*g + 0.114*b)
    

    def get_density(self,
        polygon: Polygon,
        grey_value: int
    ) -> int:
        laser_diameter = 2 # In mm
        xx, yy = polygon.exterior.coords.xy
        xx = np.array(xx)
        yy = np.array(yy)
        x_min = xx.min()
        x_max = xx.max()
        y_min = yy.min()
        y_max = yy.max()
        
        maximum_density = max(y_max-y_min, x_max-x_min) / laser_diameter
        # print(maximum_density)
        density = int(np.interp(
            grey_value,
            [0, 255],
            [maximum_density, 0])
        )
        # print(density)
        return [x_min, y_min], [x_max, y_max], density


    def fill_with_lines(
        self,
        polygon: Polygon,
        grey_value: int,
        orientation = "diagonal"
    ) -> List[Vector]:
        
        if orientation not in ["diagonal", "anti-diagonal", "vertical", "horizontal", "cross"]:
            raise ValueError(f"fill_with_lines: wrong value for orientation: {orientation}")
            return None
    
        res = []

        low, high, density = self.get_density(polygon=polygon, grey_value=grey_value)
        # density = 1
        if density > 0:
            step = 1/density

            square_box_low = low
            width = high[0] - low[0]
            heigth = high[1] - low[1]
            square_length = max(width, heigth)
            square_box_high = [
                square_box_low[0] + square_length,
                square_box_low[1] + square_length
            ]
            grid = np.arange(0,  square_length + step, step)
            
            if orientation == "diagonal":
                
                for i in range(1, len(grid)):
                    # line = LineString([[grid[i], square_box_low[1]], [square_box_low[0], grid[i]]])
                    line = LineString([[square_box_low[0] + grid[i], square_box_low[1]], [square_box_low[0], square_box_low[1] + grid[i]]])
                    intersection = polygon.intersection(line)
                    # print(intersection)
                    if isinstance(intersection, MultiLineString):
                        # x,y = intersection.xy
                        for l in intersection.geoms:
                            if not l.is_empty:
                                res.append(l)
                    else:
                        # x,y = intersection.xy
                        if not intersection.is_empty:
                            res.append(intersection)

                for i in range(1, len(grid)-1):
                    # line = LineString([[square_box_high[0], grid[i]], [grid[i], square_box_high[1]]])
                    line = LineString([[square_box_high[0] - grid[i], square_box_high[1]], [square_box_high[0], square_box_high[1] - grid[i]]])
                    intersection = polygon.intersection(line)
                    
                    if isinstance(intersection, MultiLineString):
                        # x,y = intersection.xy
                        for l in intersection.geoms:
                            if not l.is_empty:
                                res.append(l)
                    else:
                        # x,y = intersection.xy
                        if not intersection.is_empty:
                            res.append(intersection)
        return res


    def fill_with_points(
        self,
        polygon: Polygon,
        grey_value: int
    ) -> List[Vector]:
        """
        Generate random points inside the polygon

        Args:
            polygon (Polygon): The polygon inside of which the points are randomly generated
            grey_value (int) [0-255]: The grey scale value that defines the density of the points

        Returns:
            List[Tuple[float, float]]: The list of tuples (x_i, y_i)
        """
        
        low, high, density = self.get_density(polygon=polygon, grey_value=grey_value)
        
        sample = np.random.uniform(
            low=low,
            high=high,
            size=(density*density,2)
        )

        sample = sample[sample[:, 0].argsort()]

        res = []
        for point in sample:
            if polygon.contains(Point(point[0], point[1])):
                res.append(Vector(point[0], point[1]))
        
        if len(res) > 0:
            print(f"Generated {len(res)} points for polygon with grey_value = {grey_value}, density = {density}")
        return res


    def append_areas(self, areas: List[dict]):
        """
        An aera has the following structure: {"curves" : List[Curve], "color": str}
        The curves define the outlines and the color defines the density of points that will be drawn
        """
        
        for area in areas:
            edges = []
            for curve in area["curves"]:
                line_chain = LineSegmentChain()
                approximation = LineSegmentChain.line_segment_approximation(curve)
                # print(approximation)
                line_chain.extend(approximation)
                # print(line_chain._curves)
                # edges.extend([(l.start, l.end) for l in line_chain._curves])
                edges.extend([(l.start.x, l.start.y) for l in line_chain._curves])
            polygon = Polygon(edges)
            self.append_polygon(
                polygon=polygon,
                grey_value=self.color_to_grey(area["color"]),
                fill_method="diagonal"
            )
