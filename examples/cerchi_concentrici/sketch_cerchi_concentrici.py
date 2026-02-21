import math
import pathlib

import vpype as vp
import vsketch
from shapely.geometry import box
from shapely.geometry import Point as ShapelyPoint


class CerchiConcentrociSketch(vsketch.SketchClass):
    # Canvas configuration
    format_type = vsketch.Param("a4", choices=["a1", "a2", "a3", "a4", "a5", "custom"])
    landscape = vsketch.Param(False)
    custom_width_mm = vsketch.Param(210.0, 1.0, decimals=1)
    custom_height_mm = vsketch.Param(297.0, 1.0, decimals=1)

    # Circle configuration
    margin_mm = vsketch.Param(10.0, 0.0, decimals=1)
    line_spacing_mm = vsketch.Param(5.0, 0.1, decimals=2)
    start_radius_mm = vsketch.Param(5.0, 0.1, decimals=2)
    num_levels = vsketch.Param(1, 1)
    casualita_mm = vsketch.Param(30.0, 0.0, decimals=1)
    spacing_random_mm = vsketch.Param(0.0, 0.0, decimals=2)

    # G-code generation
    generate_gcode = vsketch.Param(False)
    gcode_pause_between_layers = vsketch.Param(False)
    gcode_penup = vsketch.Param(0.0, -15.0, 15.0, decimals=1)
    gcode_pendown = vsketch.Param(5.0, -15.0, 15.0, decimals=1)
    gcode_speed = vsketch.Param(2500, 100, 10000)
    gcode_margin = vsketch.Param(0, 0, 50)

    def draw(self, vsk: vsketch.Vsketch) -> None:
        # Setup canvas
        if self.format_type == "custom":
            vsk.size(f"{self.custom_width_mm}mm", f"{self.custom_height_mm}mm", center=False)
        else:
            vsk.size(self.format_type, landscape=self.landscape, center=False)

        vsk.scale("mm")

        # Get canvas dimensions in mm
        px_per_mm = vp.convert_length("1mm")
        width = vsk.width / px_per_mm
        height = vsk.height / px_per_mm

        # Center of the canvas
        cx = width / 2
        cy = height / 2

        if self.start_radius_mm <= 0 or self.line_spacing_mm <= 0:
            return

        # Clip boundary: canvas inset by margin_mm
        clip_rect = box(
            self.margin_mm,
            self.margin_mm,
            width - self.margin_mm,
            height - self.margin_mm,
        )

        for level in range(self.num_levels):
            # Each level is drawn on its own layer (1-based)
            vsk.stroke(level + 1)

            # Level 0 is centered; subsequent levels are offset randomly on X or Y
            if level == 0 or self.casualita_mm == 0:
                lx, ly = cx, cy
            else:
                # Alternate axis: odd levels shift X, even levels shift Y
                offset = vsk.random(-self.casualita_mm, self.casualita_mm)
                if level % 2 == 1:
                    lx = cx + offset
                    ly = cy
                else:
                    lx = cx
                    ly = cy + offset

            # Max radius: distance from this level's center to the farthest corner
            # of the clip rect, so circles fill the entire canvas
            corners = [
                (self.margin_mm, self.margin_mm),
                (width - self.margin_mm, self.margin_mm),
                (self.margin_mm, height - self.margin_mm),
                (width - self.margin_mm, height - self.margin_mm),
            ]
            max_radius = max(
                math.sqrt((lx - cx_) ** 2 + (ly - cy_) ** 2)
                for cx_, cy_ in corners
            )

            # Draw concentric circles for this level, clipped to the canvas rect
            radius = self.start_radius_mm
            while radius <= max_radius:
                circle_ring = ShapelyPoint(lx, ly).buffer(radius, resolution=256).boundary
                # Compute next step: each circle gets its own independent random offset
                # (symmetric: can be smaller or larger than line_spacing_mm)
                if self.spacing_random_mm > 0:
                    step = self.line_spacing_mm + vsk.random(-self.spacing_random_mm, self.spacing_random_mm)
                    step = max(step, 0.3)  # never collapse circles on top of each other
                else:
                    step = self.line_spacing_mm
                clipped = circle_ring.intersection(clip_rect)
                if not clipped.is_empty:
                    vsk.geometry(clipped)
                radius += step

    def finalize(self, vsk: vsketch.Vsketch) -> None:
        vsk.vpype("linesort")

        if self.generate_gcode:
            # Resolve canvas dimensions in mm
            if self.format_type == "custom":
                width = int(round(self.custom_width_mm))
                height = int(round(self.custom_height_mm))
            else:
                format_sizes = {
                    "a1": (594, 841),
                    "a2": (420, 594),
                    "a3": (297, 420),
                    "a4": (210, 297),
                    "a5": (148, 210),
                }
                w, h = format_sizes.get(self.format_type.lower(), (210, 297))
                if self.landscape:
                    width, height = h, w
                else:
                    width, height = w, h

            output_dir = pathlib.Path(__file__).parent / "output"
            svg2gcode_script = pathlib.Path(__file__).parents[2] / "svg2gcode.sh"

            try:
                rel_output_dir = output_dir.relative_to(svg2gcode_script.parent)
            except ValueError:
                rel_output_dir = output_dir

            latest_svg_cmd = f'$(ls -t {rel_output_dir}/*.svg | head -1)'

            script_lines = [
                "#!/usr/bin/env bash",
                "set -e",
                f"# Auto-generated by cerchi_concentrici — {self.num_levels} livello/i",
                "",
                f'cd "{svg2gcode_script.parent}"',
                f"LATEST_SVG={latest_svg_cmd}",
                'echo "Using SVG: $LATEST_SVG"',
                "",
                f'./svg2gcode.sh "$LATEST_SVG" {self.gcode_penup} {self.gcode_pendown} {self.gcode_speed} {width} {height} {self.gcode_margin}',
                "",
            ]

            if self.gcode_pause_between_layers and self.num_levels > 1:
                script_lines += [
                    "# Insert M0; before each layer boundary (except the first)",
                    'GCODE="${LATEST_SVG%.svg}.gcode"',
                    """awk 'BEGIN{first=1} /^; --- Layer /{if(!first){print "M0;"} first=0} {print}' "$GCODE" > "${GCODE}.tmp" && mv "${GCODE}.tmp" "$GCODE" """,
                    'echo "M0; pause inserted between layers"',
                    "",
                ]

            script_lines.append('echo "Done!"')

            script_content = "\n".join(script_lines) + "\n"

            sh_path = pathlib.Path(__file__).parent / "export_gcode.sh"
            sh_path.write_text(script_content)
            sh_path.chmod(0o755)

            print(f"\n{'='*70}")
            print(f"G-CODE GENERATION — {self.num_levels} LIVELLO/I")
            print(f"{'='*70}")
            print(f"\nScript salvato in: {sh_path}")
            print(f"\nEsegui con:")
            print(f"  bash {sh_path}")
            print(f"{'='*70}\n")


if __name__ == "__main__":
    CerchiConcentrociSketch.display()
