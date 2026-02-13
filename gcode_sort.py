#!/usr/bin/env python3
"""
G-code Path Sorter
Sorts G-code paths by X or Y coordinate to optimize plotter movement.
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple, Optional


class GCodeSegment:
    """Represents a continuous drawing segment (pen down to pen up)"""
    
    def __init__(self):
        self.lines: List[str] = []
        self.start_x: Optional[float] = None
        self.start_y: Optional[float] = None
        self.layer_comment: Optional[str] = None
    
    def add_line(self, line: str):
        """Add a line to this segment"""
        self.lines.append(line)
        
        # Extract first X,Y coordinates if not yet set
        if self.start_x is None:
            match = re.search(r'X([-\d.]+)', line)
            if match:
                self.start_x = float(match.group(1))
        
        if self.start_y is None:
            match = re.search(r'Y([-\d.]+)', line)
            if match:
                self.start_y = float(match.group(1))
    
    def set_layer(self, comment: str):
        """Set the layer comment for this segment"""
        self.layer_comment = comment
    
    def get_sort_key_x(self) -> Tuple[float, float]:
        """Return sort key for X-first sorting (left to right columns, then top to bottom)"""
        return (self.start_x or 0, self.start_y or 0)
    
    def get_sort_key_y(self) -> float:
        """Return Y coordinate for initial sorting"""
        return self.start_y or 0
    
    def get_end_coordinates(self) -> Tuple[Optional[float], Optional[float]]:
        """Extract end X,Y coordinates from the last drawing command"""
        # Look backwards for the last G1 command with coordinates
        for line in reversed(self.lines):
            if 'G1' in line or 'G01' in line:
                x_match = re.search(r'X([-\d.]+)', line)
                y_match = re.search(r'Y([-\d.]+)', line)
                if x_match or y_match:
                    end_x = float(x_match.group(1)) if x_match else None
                    end_y = float(y_match.group(1)) if y_match else None
                    return end_x, end_y
        return None, None
    
    def reverse_direction(self):
        """Reverse the drawing direction of this segment (swap start and end)"""
        end_x, end_y = self.get_end_coordinates()
        
        if end_x is None and end_y is None:
            return  # Nothing to reverse
        
        # Store original start coordinates
        orig_start_x = self.start_x
        orig_start_y = self.start_y
        
        # Update the segment lines
        new_lines = []
        
        for line in self.lines:
            # Update Initial position line
            if 'Initial position' in line:
                new_line = line
                if end_x is not None:
                    new_line = re.sub(r'X[-\d.]+', f'X{end_x:.3f}', new_line)
                if end_y is not None:
                    new_line = re.sub(r'Y[-\d.]+', f'Y{end_y:.3f}', new_line)
                new_lines.append(new_line)
            # Update G1 drawing command to go to original start position
            elif 'G1' in line and ('X' in line or 'Y' in line):
                new_line = line
                if orig_start_x is not None:
                    new_line = re.sub(r'X[-\d.]+', f'X{orig_start_x:.3f}', new_line)
                if orig_start_y is not None:
                    new_line = re.sub(r'Y[-\d.]+', f'Y{orig_start_y:.3f}', new_line)
                new_lines.append(new_line)
            else:
                new_lines.append(line)
        
        self.lines = new_lines
        # Update start coordinates to the new start (after reversal)
        # This is critical for sorting to work correctly!
        if end_x is not None:
            self.start_x = end_x
        if end_y is not None:
            self.start_y = end_y



def parse_gcode(content: str) -> Tuple[List[str], List[GCodeSegment], List[str]]:
    """
    Parse G-code into header, segments, and footer.
    
    Returns:
        header: Lines before first segment
        segments: List of drawing segments
        footer: Lines after last segment
    """
    lines = content.split('\n')
    header = []
    segments = []
    footer = []
    
    current_segment = None
    current_layer = None
    footer_started = False
    in_header = True
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Detect layer comments
        if stripped.startswith('; --- Layer'):
            current_layer = stripped
            if in_header:
                header.append(line)
            i += 1
            continue
        
        # Check for document end markers
        if 'G00 X0 Y0' in stripped or 'G0 X0 Y0' in stripped:
            footer_started = True
            in_header = False
        
        if footer_started:
            footer.append(line)
            i += 1
            continue
        
        # Look for "Initial position" to start a new segment
        if 'Initial position' in stripped:
            in_header = False
            # Start collecting segment
            current_segment = GCodeSegment()
            if current_layer:
                current_segment.set_layer(current_layer)
            
            # Go back to include the previous line (pen up move)
            if i > 0:
                prev_line = lines[i-1]
                if 'Z' in prev_line:
                    current_segment.add_line(prev_line)
            
            # Add current line (G0 X... Y... ; Initial position)
            current_segment.add_line(line)
            
            # Continue adding lines until we find "pen up"
            i += 1
            while i < len(lines):
                line = lines[i]
                current_segment.add_line(line)
                
                if 'pen up' in line.lower():
                    # Segment complete
                    segments.append(current_segment)
                    current_segment = None
                    break
                i += 1
            i += 1
            continue
        
        # Add to header if still in header
        if in_header:
            header.append(line)
        
        i += 1
    
    return header, segments, footer


def sort_gcode(input_file: str, output_file: str, sort_by: str = 'y', fix_direction: bool = True):
    """
    Sort G-code segments by X or Y coordinate and optionally ensure all lines are drawn
    in the correct direction (top to bottom, left to right).
    
    Args:
        input_file: Input G-code file path
        output_file: Output G-code file path
        sort_by: 'x' for left-to-right, 'y' for top-to-bottom
        fix_direction: If True, reverse segments to ensure correct drawing direction
    """
    # Read input file
    with open(input_file, 'r') as f:
        content = f.read()
    
    # Parse G-code
    header, segments, footer = parse_gcode(content)
    
    if not segments:
        print("Warning: No segments found in G-code file")
        with open(output_file, 'w') as f:
            f.write(content)
        return
    
    # FIRST correct direction if requested (updates start_x/start_y)
    reversed_count = 0
    if fix_direction:
        for segment in segments:
            end_x, end_y = segment.get_end_coordinates()
            
            # Check if segment needs to be reversed
            # Always ensure: X increases (left to right) AND Y increases (top to bottom)
            should_reverse = False
            
            # Check X direction
            if end_x is not None and segment.start_x is not None:
                if end_x < segment.start_x:  # Going leftward
                    should_reverse = True
            
            # Check Y direction (only if X is ok or equal)
            if not should_reverse and end_y is not None and segment.start_y is not None:
                if end_y < segment.start_y:  # Going upward
                    should_reverse = True
            
            if should_reverse:
                segment.reverse_direction()
                reversed_count += 1
    
    # THEN sort segments using updated coordinates
    if sort_by.lower() == 'x':
        segments.sort(key=lambda s: s.get_sort_key_x())
        sort_desc = "X (left to right, then top to bottom)"
    else:
        # For Y sorting: create separate rows with strict Y boundaries
        # 1. Sort all segments by Y coordinate (top to bottom)
        segments.sort(key=lambda s: s.get_sort_key_y())
        
        # 2. Group segments into rows with fixed Y boundaries
        if not segments:
            sort_desc = "Y (row-by-row, left to right)"
        else:
            rows = []
            row_y_tolerance = 10.0  # Maximum Y range within a single row
            
            for segment in segments:
                if segment.start_y is None:
                    if rows:
                        rows[-1].append(segment)
                    else:
                        rows.append([segment])
                    continue
                
                # Try to find a row where this segment fits (based on FIRST segment in row)
                placed = False
                for row in rows:
                    # Get the Y of the FIRST segment in the row (defines row boundaries)
                    first_seg = row[0]
                    if first_seg.start_y is None:
                        row.append(segment)
                        placed = True
                        break
                    
                    # Check if segment's Y is within tolerance of first segment's Y
                    if abs(segment.start_y - first_seg.start_y) <= row_y_tolerance:
                        row.append(segment)
                        placed = True
                        break
                
                # If not placed in existing row, create new row
                if not placed:
                    rows.append([segment])
            
            # 3. Sort each row by X (left to right)
            sorted_segments = []
            for row in rows:
                row.sort(key=lambda s: s.start_x or 0)
                sorted_segments.extend(row)
            
            segments = sorted_segments
            sort_desc = f"Y (row-by-row with {len(rows)} rows, left to right)"
    
    # Write output file
    with open(output_file, 'w') as f:
        # Write header
        f.write('\n'.join(header))
        if header and not header[-1].endswith('\n'):
            f.write('\n')
        
        # Add sorting comment
        f.write(f'; Paths sorted by {sort_desc}\n')
        f.write(f'; Total segments: {len(segments)}\n')
        if fix_direction:
            f.write(f'; Direction correction: ENABLED (reversed {reversed_count} segments)\n\n')
        else:
            f.write(f'; Direction correction: DISABLED\n\n')
        
        # Write sorted segments
        current_layer = None
        for i, segment in enumerate(segments):
            # Write layer comment if it changed
            if segment.layer_comment and segment.layer_comment != current_layer:
                f.write(f'\n{segment.layer_comment}\n')
                current_layer = segment.layer_comment
            
            # Write segment lines
            for line in segment.lines:
                f.write(line)
                if not line.endswith('\n'):
                    f.write('\n')
        
        # Write footer
        if footer:
            f.write('\n')
            f.write('\n'.join(footer))
    
    print(f"✓ G-code sorted by {sort_desc}")
    print(f"  Input:  {input_file}")
    print(f"  Output: {output_file}")
    print(f"  Segments: {len(segments)}")
    if fix_direction:
        print(f"  Reversed: {reversed_count} segments to ensure correct direction")
    else:
        print(f"  Direction correction: disabled")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python gcode_sort.py <input.gcode> [x|y] [--no-fix] [output.gcode]")
        print()
        print("Arguments:")
        print("  input.gcode   - Input G-code file")
        print("  x|y          - Sort by X (left-to-right) or Y (top-to-bottom), default: y")
        print("  --no-fix     - Disable direction correction (lines drawn as-is)")
        print("  output.gcode - Output file, default: input_sorted.gcode")
        print()
        print("Examples:")
        print("  python gcode_sort.py file.gcode")
        print("  python gcode_sort.py file.gcode x")
        print("  python gcode_sort.py file.gcode y --no-fix")
        print("  python gcode_sort.py file.gcode y output.gcode")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    # Parse arguments
    sort_by = 'y'
    fix_direction = True
    output_file = None
    
    for i in range(2, len(sys.argv)):
        arg = sys.argv[i]
        if arg in ['x', 'y']:
            sort_by = arg
        elif arg == '--no-fix':
            fix_direction = False
        elif not output_file:
            output_file = arg
    
    # Determine output filename if not specified
    if not output_file:
        input_path = Path(input_file)
        output_file = str(input_path.parent / f"{input_path.stem}_sorted{input_path.suffix}")
    
    # Check input file exists
    if not Path(input_file).exists():
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)
    
    # Sort the G-code
    sort_gcode(input_file, output_file, sort_by, fix_direction)


if __name__ == "__main__":
    main()
