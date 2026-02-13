#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from gcode_sort import parse_gcode

# Read file
with open('examples/random_lines_vert/output/random_lines_liked_7.gcode', 'r') as f:
    content = f.read()

header, segments, footer = parse_gcode(content)

# Sort by Y
segments_sorted = sorted(segments, key=lambda s: (s.start_y or 0, s.start_x or 0))

print(f"Total segments: {len(segments_sorted)}")
print("\nFirst 15 segments after Y sorting:")
for i, seg in enumerate(segments_sorted[:15]):
    # Find Initial position line
    init_line = [l for l in seg.lines if 'Initial position' in l][0] if any('Initial position' in l for l in seg.lines) else "???"
    print(f"{i+1}. start_y={seg.start_y:.3f}, start_x={seg.start_x:.3f} | {init_line.strip()}")
