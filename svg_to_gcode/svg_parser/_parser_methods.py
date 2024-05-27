from xml.etree import ElementTree
from typing import List, Tuple
from copy import deepcopy

from svg_to_gcode.svg_parser import Path, Transformation
from svg_to_gcode.geometry import Curve

NAMESPACES = {'svg': 'http://www.w3.org/2000/svg'}


def _has_style(element: ElementTree.Element, key: str, value: str) -> bool:
    """
    Check if an element contains a specific key and value either as an independent attribute or in the style attribute.
    """
    return element.get(key) == value or (element.get("style") and f"{key}:{value}" in element.get("style"))

def is_path_filled(style):
    return "fill:" in style

# Todo deal with viewBoxes
def parse_root_custom(root: ElementTree.Element, transform_origin=False, canvas_height=None, draw_hidden=False,
               visible_root=True, root_transformation=None) -> Tuple[List[Curve], List[dict]]:

    """
    Recursively parse an etree root's children into geometric curves.

    :param root: The etree element who's children should be recursively parsed. The root will not be drawn.
    :param canvas_height: The height of the canvas. By default the height attribute of the root is used. If the root
    does not contain the height attribute, it must be either manually specified or transform must be False.
    :param transform_origin: Whether or not to transform input coordinates from the svg coordinate system to standard
    cartesian system. Depends on canvas_height for calculations.
    :param draw_hidden: Whether or not to draw hidden elements based on their display, visibility and opacity attributes.
    :param visible_root: Specifies whether or the root is visible. (Inheritance can be overridden)
    :param root_transformation: Specifies whether the root's transformation. (Transformations are inheritable)
    :return: A list of geometric curves describing the svg. Use the Compiler sub-module to compile them to gcode.
    """
    curves = []
    areas = []
    
    if canvas_height is None:
        height_str = root.get("height")
        canvas_height = float(height_str) if height_str.isnumeric() else float(height_str[:-2])

    # Draw visible elements (Depth-first search)
    for element in list(root):

        # display cannot be overridden by inheritance. Just skip the element
        display = _has_style(element, "display", "none")

        if display or element.tag == "{%s}defs" % NAMESPACES["svg"]:
            continue

        transformation = deepcopy(root_transformation) if root_transformation else None

        transform = element.get('transform')
        if transform:
            transformation = Transformation() if transformation is None else transformation
            transformation.add_transform(transform)

        # Is the element and it's root not hidden?
        visible = visible_root and not (_has_style(element, "visibility", "hidden")
                                        or _has_style(element, "visibility", "collapse"))
        # Override inherited visibility
        visible = visible or (_has_style(element, "visibility", "visible"))

        
        
        # If the current element is opaque and visible, draw it
        if draw_hidden or visible:
            if element.tag == "{%s}path" % NAMESPACES["svg"]:
                style = element.attrib['style']
                path_color = get_color(style, attribute="fill")
                print(path_color)
                cut = (path_color in ["#ff0000", "red"])
                path = Path(element.attrib['d'], canvas_height, transform_origin, transformation, cut=cut)
                curves.extend(path.curves)
                
                if path.closed and is_path_filled(style):
                    area_color = get_color(style, attribute="fill")
                    areas.extend([{"curves": path.curves, "color": area_color}])


        # curves.extend(parse_root_custom(element, transform_origin, canvas_height, draw_hidden, visible, transformation))
        curves_rec, areas_rec = parse_root_custom(element, transform_origin, canvas_height, draw_hidden, visible, transformation)
        curves.extend(curves_rec)
        areas.extend(areas_rec)

    # ToDo implement shapes class
    return curves, areas

    
    
def parse_root(root: ElementTree.Element, transform_origin=True, canvas_height=None, draw_hidden=False,
               visible_root=True, root_transformation=None) -> List[Curve]:

    """
    Recursively parse an etree root's children into geometric curves.

    :param root: The etree element who's children should be recursively parsed. The root will not be drawn.
    :param canvas_height: The height of the canvas. By default the height attribute of the root is used. If the root
    does not contain the height attribute, it must be either manually specified or transform must be False.
    :param transform_origin: Whether or not to transform input coordinates from the svg coordinate system to standard
    cartesian system. Depends on canvas_height for calculations.
    :param draw_hidden: Whether or not to draw hidden elements based on their display, visibility and opacity attributes.
    :param visible_root: Specifies whether or the root is visible. (Inheritance can be overridden)
    :param root_transformation: Specifies whether the root's transformation. (Transformations are inheritable)
    :return: A list of geometric curves describing the svg. Use the Compiler sub-module to compile them to gcode.
    """
    

    if canvas_height is None:
        height_str = root.get("height")
        canvas_height = float(height_str) if height_str.isnumeric() else float(height_str[:-2])

    curves = []

    # Draw visible elements (Depth-first search)
    for element in list(root):

        # display cannot be overridden by inheritance. Just skip the element
        display = _has_style(element, "display", "none")

        if display or element.tag == "{%s}defs" % NAMESPACES["svg"]:
            continue

        transformation = deepcopy(root_transformation) if root_transformation else None

        transform = element.get('transform')
        if transform:
            transformation = Transformation() if transformation is None else transformation
            transformation.add_transform(transform)

        # Is the element and it's root not hidden?
        visible = visible_root and not (_has_style(element, "visibility", "hidden")
                                        or _has_style(element, "visibility", "collapse"))
        # Override inherited visibility
        visible = visible or (_has_style(element, "visibility", "visible"))

        # If the current element is opaque and visible, draw it
        if draw_hidden or visible:
            if element.tag == "{%s}path" % NAMESPACES["svg"]:
                path = Path(element.attrib['d'], canvas_height, transform_origin, transformation)
                curves.extend(path.curves)
        # Continue the recursion
        curves.extend(parse_root(element, transform_origin, canvas_height, draw_hidden, visible, transformation))

    # ToDo implement shapes class
    return curves

 

def get_color(style: str, attribute: str):
    """
    Warning, there is no "fill" for black objects
    """
    color = "#000000"
    s = style.split(";")
    for x in s:
        if f"{attribute}:" in x:
            color = x.replace(f"{attribute}:", "")
            break
    return color


def parse_string(svg_string: str, transform_origin=True, canvas_height=None, draw_hidden=False) -> List[Curve]:
    """
        Recursively parse an svg string into geometric curves. (Wrapper for parse_root)

        :param svg_string: The etree element who's children should be recursively parsed. The root will not be drawn.
        :param canvas_height: The height of the canvas. By default the height attribute of the root is used. If the root
        does not contain the height attribute, it must be either manually specified or transform_origin must be False.
        :param transform_origin: Whether or not to transform input coordinates from the svg coordinate system to standard cartesian
         system. Depends on canvas_height for calculations.
        :param draw_hidden: Whether or not to draw hidden elements based on their display, visibility and opacity attributes.
        :return: A list of geometric curves describing the svg. Use the Compiler sub-module to compile them to gcode.
    """
    root = ElementTree.fromstring(svg_string)
    return parse_root(root, transform_origin, canvas_height, draw_hidden)


def parse_file(file_path: str, transform_origin=True, canvas_height=None, draw_hidden=False) -> List[Curve]:
    """
            Recursively parse an svg file into geometric curves. (Wrapper for parse_root)

            :param file_path: The etree element who's children should be recursively parsed. The root will not be drawn.
            :param canvas_height: The height of the canvas. By default the height attribute of the root is used. If the root
            does not contain the height attribute, it must be either manually specified or transform_origin must be False.
            :param transform_origin: Whether or not to transform input coordinates from the svg coordinate system to standard cartesian
             system. Depends on canvas_height for calculations.
            :param draw_hidden: Whether or not to draw hidden elements based on their display, visibility and opacity attributes.
            :return: A list of geometric curves describing the svg. Use the Compiler sub-module to compile them to gcode.
        """
    root = ElementTree.parse(file_path).getroot()
    return parse_root(root, transform_origin, canvas_height, draw_hidden)


def parse_file_custom(file_path: str, transform_origin=False, canvas_height=None, draw_hidden=False) -> Tuple[List[Curve], List[dict]]:
    """
            Recursively parse an svg file into geometric curves. (Wrapper for parse_root)

            :param file_path: The etree element who's children should be recursively parsed. The root will not be drawn.
            :param canvas_height: The height of the canvas. By default the height attribute of the root is used. If the root
            does not contain the height attribute, it must be either manually specified or transform_origin must be False.
            :param transform_origin: Whether or not to transform input coordinates from the svg coordinate system to standard cartesian
             system. Depends on canvas_height for calculations.
            :param draw_hidden: Whether or not to draw hidden elements based on their display, visibility and opacity attributes.
            :return: A list of geometric curves describing the svg. Use the Compiler sub-module to compile them to gcode.
        """
    print("Parsing file...")
    root = ElementTree.parse(file_path).getroot()
    return parse_root_custom(root, transform_origin, canvas_height, draw_hidden)
    

