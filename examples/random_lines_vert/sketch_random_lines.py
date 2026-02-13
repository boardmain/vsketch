import numpy as np
import pathlib

import vpype as vp
import vsketch


class RandomLinesSketch(vsketch.SketchClass):
    # Canvas configuration
    format_type = vsketch.Param("a4", choices=["a1", "a2", "a3", "a4", "a5", "custom"])
    landscape = vsketch.Param(True)
    custom_width_mm = vsketch.Param(210.0, 1.0, decimals=1)
    custom_height_mm = vsketch.Param(297.0, 1.0, decimals=1)
    
    # Line configuration
    top_margin_mm = vsketch.Param(0.0, 0.0, decimals=1)
    x_margin_mm = vsketch.Param(0.0, 0.0, decimals=1)
    show_lines = vsketch.Param(True)
    replicate_first_line = vsketch.Param(False)
    num_line = vsketch.Param(200, 1)
    line_spacing_mm = vsketch.Param(1.8, 0.1, decimals=2)
    y_amplitude_mm = vsketch.Param(5.0, 0.0, decimals=2)
    x_freq = vsketch.Param(0.25)
    y_freq = vsketch.Param(4)
    
    # Point configuration
    show_points = vsketch.Param(True)
    points_per_line = vsketch.Param(0, 0)
    point_spacing_mm = vsketch.Param(10.0, 0.1, decimals=2)
    point_x_offset_mm = vsketch.Param(0.0, 0.0, decimals=2)
    show_vertical_lines = vsketch.Param(True)
    vertical_line_length_mm = vsketch.Param(0.0, 0.0, decimals=2)
    
    # G-code generation
    generate_gcode = vsketch.Param(False)
    gcode_penup = vsketch.Param(0.0, -15.0, 15.0, decimals=1)
    gcode_pendown = vsketch.Param(5.0, -15.0, 15.0, decimals=1)
    gcode_speed = vsketch.Param(2500, 100, 10000)
    gcode_margin = vsketch.Param(0, 0, 50)

    def draw(self, vsk: vsketch.Vsketch) -> None:
        # Setup canvas size (center=False prevents auto-centering which causes
        # lines to shift when toggling vertical lines visibility)
        if self.format_type == "custom":
            vsk.size(f"{self.custom_width_mm}mm", f"{self.custom_height_mm}mm", center=False)
        else:
            vsk.size(self.format_type, landscape=self.landscape, center=False)
        
        vsk.scale("mm")
        
        # Get canvas dimensions in mm (vsk.width/height are in CSS pixels, convert to mm)
        px_per_mm = vp.convert_length("1mm")
        width = vsk.width / px_per_mm
        height = vsk.height / px_per_mm

        x_coords = np.linspace(0, width, 1000)

        # Apply X margin: filter coords to draw only within margins
        x_margin_left = self.x_margin_mm
        x_margin_right = width - self.x_margin_mm
        x_mask = (x_coords >= x_margin_left) & (x_coords <= x_margin_right)
        x_coords_clipped = x_coords[x_mask]

        perlin = vsk.noise(
            x_coords * self.x_freq / 10.0, np.arange(self.num_line) / self.num_line * self.y_freq
        )

        # Draw lines first (clipped to canvas) if enabled
        if self.show_lines:
            if self.replicate_first_line:
                # Generate only the first line pattern and replicate it
                first_line_y = (perlin[:, 0] - 0.5) * self.y_amplitude_mm
                
                for i in range(self.num_line):
                    base_y = self.top_margin_mm + self.line_spacing_mm * i
                    # Skip lines whose base position is beyond the canvas
                    if base_y > height:
                        break
                    # Use the same pattern, just shifted vertically
                    y_coords = first_line_y + base_y
                    y_coords = np.clip(y_coords, 0, height)
                    # Apply X margin
                    vsk.polygon(x_coords_clipped, y_coords[x_mask])
            else:
                # Normal behavior: each line has its own noise pattern
                for i in range(self.num_line):
                    base_y = self.top_margin_mm + self.line_spacing_mm * i
                    # Skip lines whose base position is beyond the canvas
                    if base_y > height:
                        break
                    y_coords = (perlin[:, i] - 0.5) * self.y_amplitude_mm + base_y
                    y_coords = np.clip(y_coords, 0, height)
                    # Apply X margin
                    vsk.polygon(x_coords_clipped, y_coords[x_mask])
        
        # Pre-generate random X offsets per row (deterministic based on row index)
        # Row 0: no offset, odd rows: random between 0 and +offset, even rows (>0): random between -offset and 0
        rng = np.random.RandomState(42)
        row_x_offsets = np.zeros(self.num_line)
        if self.point_x_offset_mm > 0:
            for i in range(1, self.num_line):
                rand_val = rng.random()  # 0..1
                if i % 2 == 1:  # odd rows: positive offset
                    row_x_offsets[i] = rand_val * self.point_x_offset_mm
                else:  # even rows (>0): negative offset
                    row_x_offsets[i] = -rand_val * self.point_x_offset_mm

        # Draw red points on lines if enabled
        if self.show_points and self.points_per_line > 0:
            vsk.stroke(2)  # Switch to layer 2 for red points
            vsk.penWidth("0.3mm", 2)
            
            # Calculate centered point positions
            if self.points_per_line == 1:
                # Single point centered
                point_x_positions = np.array([width / 2])
            else:
                # Multiple points centered with spacing
                total_width = (self.points_per_line - 1) * self.point_spacing_mm
                start_x = (width - total_width) / 2
                point_x_positions = np.array([start_x + i * self.point_spacing_mm 
                                              for i in range(self.points_per_line)])
            
            for i in range(self.num_line):
                base_y = self.top_margin_mm + self.line_spacing_mm * i
                # Skip lines beyond canvas
                if base_y > height:
                    break
                # Interpolate y coordinates for the point positions
                if self.replicate_first_line:
                    y_line = (perlin[:, 0] - 0.5) * self.y_amplitude_mm + base_y
                else:
                    y_line = (perlin[:, i] - 0.5) * self.y_amplitude_mm + base_y
                
                # Clip y coordinates to canvas bounds
                y_line = np.clip(y_line, 0, height)
                
                # Apply random X offset for this row
                shifted_x = point_x_positions + row_x_offsets[i]
                shifted_x = np.clip(shifted_x, x_margin_left, x_margin_right)
                y_points = np.interp(shifted_x, x_coords, y_line)
                
                # Draw small circles at each point position
                for x, y in zip(shifted_x, y_points):
                    if 0 <= y <= height and x_margin_left <= x <= x_margin_right:
                        vsk.circle(x, y, radius=0.5)
        
        # Draw vertical lines from points if enabled
        if self.show_vertical_lines and self.points_per_line > 0 and self.vertical_line_length_mm > 0:
            vsk.stroke(3)  # Switch to layer 3 for vertical lines (blue)
            vsk.penWidth("0.3mm", 3)
            
            # Calculate centered point positions (same as before)
            if self.points_per_line == 1:
                point_x_positions = np.array([width / 2])
            else:
                total_width = (self.points_per_line - 1) * self.point_spacing_mm
                start_x = (width - total_width) / 2
                point_x_positions = np.array([start_x + i * self.point_spacing_mm 
                                              for i in range(self.points_per_line)])
            
            for i in range(self.num_line):
                base_y = self.top_margin_mm + self.line_spacing_mm * i
                # Skip lines beyond canvas
                if base_y > height:
                    break
                # Interpolate y coordinates for the point positions
                if self.replicate_first_line:
                    y_line = (perlin[:, 0] - 0.5) * self.y_amplitude_mm + base_y
                else:
                    y_line = (perlin[:, i] - 0.5) * self.y_amplitude_mm + base_y
                y_line = np.clip(y_line, 0, height)
                
                # Apply random X offset for this row
                shifted_x = point_x_positions + row_x_offsets[i]
                shifted_x = np.clip(shifted_x, x_margin_left, x_margin_right)
                y_points = np.interp(shifted_x, x_coords, y_line)
                
                # Calculate next row's points if it exists
                y_next_points = None
                if i < self.num_line - 1:
                    next_base_y = self.top_margin_mm + self.line_spacing_mm * (i + 1)
                    if self.replicate_first_line:
                        y_line_next = (perlin[:, 0] - 0.5) * self.y_amplitude_mm + next_base_y
                    else:
                        y_line_next = (perlin[:, i + 1] - 0.5) * self.y_amplitude_mm + next_base_y
                    y_line_next = np.clip(y_line_next, 0, height)
                    # Next row has its own offset
                    next_shifted_x = point_x_positions + row_x_offsets[i + 1]
                    next_shifted_x = np.clip(next_shifted_x, x_margin_left, x_margin_right)
                    y_next_points = np.interp(next_shifted_x, x_coords, y_line_next)
                
                # Draw vertical lines from each point downward
                for j, (x, y) in enumerate(zip(shifted_x, y_points)):
                    if x < x_margin_left or x > x_margin_right:
                        continue
                    y_end = min(y + self.vertical_line_length_mm, height)
                    
                    # Limit y_end to stay at least 0.5mm before next row's point
                    if y_next_points is not None:
                        max_y_end = y_next_points[j] - 0.5
                        y_end = min(y_end, max_y_end)
                    
                    # Only draw if there's meaningful length
                    if y_end > y + 0.1:
                        vsk.line(x, y, x, y_end)

    def finalize(self, vsk: vsketch.Vsketch) -> None:
        # Only sort lines for plotting efficiency - do NOT use linemerge/linesimplify/reloop
        # as they alter geometry and cause lines to shift when toggling layers
        vsk.vpype("linesort")
        
        # Generate G-code command if enabled
        if self.generate_gcode:
            # Get canvas dimensions in mm (as integers)
            if self.format_type == "custom":
                width = int(round(self.custom_width_mm))
                height = int(round(self.custom_height_mm))
            else:
                # Map standard formats to mm dimensions (portrait orientation)
                format_sizes = {
                    "a1": (594, 841),
                    "a2": (420, 594),
                    "a3": (297, 420),
                    "a4": (210, 297),
                    "a5": (148, 210)
                }
                
                if self.format_type.lower() in format_sizes:
                    w, h = format_sizes[self.format_type.lower()]
                    # Swap if landscape
                    if self.landscape:
                        width, height = h, w
                    else:
                        width, height = w, h
                else:
                    # Fallback
                    width = int(round(vsk.width))
                    height = int(round(vsk.height))
            
            # Get paths
            output_dir = pathlib.Path(__file__).parent / "output"
            svg2gcode_script = pathlib.Path(__file__).parents[2] / "svg2gcode.sh"
            
            # Calculate relative path from svg2gcode.sh to output directory
            try:
                rel_output_dir = output_dir.relative_to(svg2gcode_script.parent)
            except ValueError:
                # If not relative, use absolute path
                rel_output_dir = output_dir
            
            # Build the command
            svg_path = f"{rel_output_dir}/<filename>.svg"
            
            # Create command that finds the latest SVG automatically
            latest_svg_cmd = f'$(ls -t {rel_output_dir}/*.svg | head -1)'
            
            # Path to gcode_sort.py
            gcode_sort_script = svg2gcode_script.parent / "gcode_sort.py"
            
            # Command to find the latest GCODE file
            latest_gcode_cmd = f'$(ls -t {rel_output_dir}/*.gcode | head -1)'
            
            print(f"\n{'='*70}")
            print(f"G-CODE GENERATION COMMANDS:")
            print(f"{'='*70}")
            print(f"\n1. Generate G-code from SVG:")
            print(f"   cd {svg2gcode_script.parent}")
            print(f'   ./svg2gcode.sh {latest_svg_cmd} {self.gcode_penup} {self.gcode_pendown} {self.gcode_speed} {width} {height} {self.gcode_margin}')
            print(f"\n2. Sort paths for optimized plotting (uses most recent G-code):")
            print(f"   cd {svg2gcode_script.parent}")
            print(f'   python3 gcode_sort.py {latest_gcode_cmd} y')
            print(f"\n💡 Step 1 automatically uses the most recent SVG in the output folder")
            print(f"💡 Step 2 automatically uses the most recent G-code and creates a _sorted.gcode file")
            print(f"\nOr specify files manually:")
            print(f"./svg2gcode.sh {svg_path} {self.gcode_penup} {self.gcode_pendown} {self.gcode_speed} {width} {height} {self.gcode_margin}")
            print(f'python3 gcode_sort.py {rel_output_dir}/<filename>.gcode y')
            print(f"{'='*70}\n")


if __name__ == "__main__":
    RandomLinesSketch.display()
