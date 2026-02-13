"""Serpentine Tubes - Organic Path Generator

Genera tracciati organici con curve morbide che crescono dal centro verso
l'esterno. Ogni tracciato è composto da linee parallele concentriche che
formano "tubi" senza mai sovrapporsi.

Il sistema funziona così:
1. Genera un percorso centrale usando curve smooth (Catmull-Rom o Bezier)
2. Crea linee parallele offset dal percorso centrale
3. Ogni linea è più lunga della precedente (crescita dal centro)
4. Nessun angolo retto, solo curve morbide
5. I tracciati non si sovrappongono mai

Parametri:
  - num_noodles : numero di tracciati da generare
  - num_tubes : numero di linee parallele per ogni tracciato
  - path_length : lunghezza del percorso centrale
  - smoothness : quanto sono morbide le curve (0.0-1.0)
  - spacing : distanza minima tra tracciati
  - tube_width : larghezza di ogni tubo
"""

import math
import numpy as np
import vsketch

# Cell types (da CellType.pde)
EMPTY = 0
VERTICAL = 1
HORIZONTAL = 2
CORNER_TL = 3
CORNER_TR = 4
CORNER_BR = 5
CORNER_BL = 6
OCCUPIED = 11
V_CROSSED = 9
H_CROSSED = 10


class Point:
    """Rappresenta un punto nella griglia con tipo e proprietà."""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.type = OCCUPIED
        self.join_type = 0  # Per variazioni grafiche


class Noodle:
    """Un tracciato serpentinante con più linee parallele."""
    
    def __init__(self, path, tile_size, thickness_pct, layer):
        self.path = path  # Lista di Point
        self.tile_size = tile_size
        self.thickness_pct = thickness_pct
        self.thickness = tile_size * thickness_pct
        self.margin = (tile_size - self.thickness) / 2
        self.layer = layer
    
    def draw(self, vsk: vsketch.Vsketch, num_tubes, allow_hidden_line=True):
        """Disegna il noodle con linee parallele concentriche come percorsi continui."""
        if not self.path or len(self.path) < 2:
            return
        
        # Disegna ogni tubo come un percorso continuo
        for tube_idx in range(num_tubes):
            # Calcola offset per questo tubo
            max_offset = self.margin
            offset = max_offset * (2 * tube_idx / max(num_tubes - 1, 1) - 1)
            
            # Costruisci il percorso continuo completo per questo tubo
            self._draw_continuous_tube(vsk, offset, allow_hidden_line)
    
    def _draw_continuous_tube(self, vsk: vsketch.Vsketch, offset, allow_hidden):
        """Disegna un tubo completo come percorso continuo."""
        # Costruisci i punti del lato sinistro (andando avanti)
        left_side = []
        # Costruisci i punti del lato destro (andando indietro)
        right_side = []
        
        for i, p in enumerate(self.path):
            if i == 0:
                # Inizio: tappo semicircolare
                pts = self._get_start_cap_points(p, self.path[1], offset)
                left_side.extend(pts['left'])
                right_side.extend(pts['right'][::-1])  # Inverti per tornare indietro
            elif i == len(self.path) - 1:
                # Fine: tappo semicircolare
                pts = self._get_end_cap_points(p, self.path[-2], offset)
                left_side.extend(pts['left'])
                right_side.extend(pts['right'][::-1])
            else:
                # Segmento intermedio
                prev = self.path[i - 1]
                next = self.path[i + 1]
                pts = self._get_segment_points(p, prev, next, offset, allow_hidden, i)
                if pts:
                    left_side.extend(pts['left'])
                    right_side.extend(pts['right'][::-1])
        
        # Crea il percorso chiuso: sinistra + destra invertita
        if left_side and right_side:
            all_points = left_side + right_side
            xs = [pt[0] for pt in all_points]
            ys = [pt[1] for pt in all_points]
            vsk.polygon(xs, ys)
    
    def _get_start_cap_points(self, pos, neighbor, offset):
        """Restituisce i punti del tappo iniziale."""
        cx = pos.x * self.tile_size + self.tile_size / 2
        cy = pos.y * self.tile_size + self.tile_size / 2
        r = (self.thickness / 2) - abs(offset)
        
        if r <= 0:
            return {'left': [], 'right': []}
        
        arc_points = 20
        
        # Determina orientamento
        if neighbor.x < pos.x:  # Verso sinistra
            t = np.linspace(math.pi / 2, 3 * math.pi / 2, arc_points)
            arc_xs = cx + r * np.cos(t)
            arc_ys = cy + r * np.sin(t)
            return {
                'left': list(zip(arc_xs[:len(arc_xs)//2], arc_ys[:len(arc_ys)//2])),
                'right': list(zip(arc_xs[len(arc_xs)//2:], arc_ys[len(arc_ys)//2:]))
            }
        elif neighbor.x > pos.x:  # Verso destra
            t = np.linspace(-math.pi / 2, math.pi / 2, arc_points)
            arc_xs = cx + r * np.cos(t)
            arc_ys = cy + r * np.sin(t)
            return {
                'left': list(zip(arc_xs[:len(arc_xs)//2], arc_ys[:len(arc_ys)//2])),
                'right': list(zip(arc_xs[len(arc_xs)//2:], arc_ys[len(arc_ys)//2:]))
            }
        elif neighbor.y < pos.y:  # Verso su
            t = np.linspace(math.pi, 2 * math.pi, arc_points)
            arc_xs = cx + r * np.cos(t)
            arc_ys = cy + r * np.sin(t)
            return {
                'left': list(zip(arc_xs[:len(arc_xs)//2], arc_ys[:len(arc_ys)//2])),
                'right': list(zip(arc_xs[len(arc_xs)//2:], arc_ys[len(arc_ys)//2:]))
            }
        else:  # Verso giù
            t = np.linspace(0, math.pi, arc_points)
            arc_xs = cx + r * np.cos(t)
            arc_ys = cy + r * np.sin(t)
            return {
                'left': list(zip(arc_xs[:len(arc_xs)//2], arc_ys[:len(arc_ys)//2])),
                'right': list(zip(arc_xs[len(arc_xs)//2:], arc_ys[len(arc_ys)//2:]))
            }
    
    def _get_end_cap_points(self, pos, neighbor, offset):
        """Restituisce i punti del tappo finale."""
        return self._get_start_cap_points(pos, neighbor, offset)
    
    def _get_segment_points(self, p, prev, next, offset, allow_hidden, idx):
        """Restituisce i punti dei bordi sinistro e destro di un segmento."""
        px = p.x * self.tile_size
        py = p.y * self.tile_size
        m = self.margin + offset
        r = (self.thickness / 2) - abs(offset)
        
        if r <= 0:
            return None
        
        # Determina direzioni
        top = prev.y < p.y or next.y < p.y
        bottom = prev.y > p.y or next.y > p.y
        left = prev.x < p.x or next.x < p.x
        right = prev.x > p.x or next.x > p.x
        
        if top and bottom:
            # Segmento verticale
            if allow_hidden and p.type == V_CROSSED:
                # Gap per hidden line removal
                gap_start = py + self.tile_size * 0.35
                gap_end = py + self.tile_size * 0.65
                return {
                    'left': [
                        (px + m, py),
                        (px + m, gap_start),
                    ],
                    'right': [
                        (px + self.tile_size - m, gap_end),
                        (px + self.tile_size - m, py + self.tile_size)
                    ]
                }
            else:
                return {
                    'left': [(px + m, py), (px + m, py + self.tile_size)],
                    'right': [(px + self.tile_size - m, py + self.tile_size), 
                             (px + self.tile_size - m, py)]
                }
                
        elif left and right:
            # Segmento orizzontale
            if allow_hidden and p.type == H_CROSSED:
                gap_start = px + self.tile_size * 0.35
                gap_end = px + self.tile_size * 0.65
                return {
                    'left': [
                        (px, py + m),
                        (gap_start, py + m),
                    ],
                    'right': [
                        (gap_end, py + self.tile_size - m),
                        (px + self.tile_size, py + self.tile_size - m)
                    ]
                }
            else:
                return {
                    'left': [(px, py + m), (px + self.tile_size, py + m)],
                    'right': [(px + self.tile_size, py + self.tile_size - m),
                             (px, py + self.tile_size - m)]
                }
        else:
            # Angolo con arco
            return self._get_corner_points(px, py, left, right, top, bottom, m, r)
    
    def _get_corner_points(self, px, py, left, right, top, bottom, m, r):
        """Restituisce i punti per un angolo curvo."""
        arc_points = 15
        ts = self.tile_size
        
        if left and bottom:
            # Angolo top-right: arco da destra verso basso
            cx, cy = px, py + ts
            t_outer = np.linspace(-math.pi / 2, 0, arc_points)
            t_inner = np.linspace(-math.pi / 2, 0, arc_points)
            outer_r = ts - m
            inner_r = m
            return {
                'left': list(zip(cx + outer_r * np.cos(t_outer), cy + outer_r * np.sin(t_outer))),
                'right': list(zip(cx + inner_r * np.cos(t_inner), cy + inner_r * np.sin(t_inner)))
            }
        elif top and left:
            # Angolo bottom-right
            cx, cy = px, py
            t_outer = np.linspace(0, math.pi / 2, arc_points)
            t_inner = np.linspace(0, math.pi / 2, arc_points)
            outer_r = ts - m
            inner_r = m
            return {
                'left': list(zip(cx + outer_r * np.cos(t_outer), cy + outer_r * np.sin(t_outer))),
                'right': list(zip(cx + inner_r * np.cos(t_inner), cy + inner_r * np.sin(t_inner)))
            }
        elif top and right:
            # Angolo bottom-left
            cx, cy = px + ts, py
            t_outer = np.linspace(math.pi / 2, math.pi, arc_points)
            t_inner = np.linspace(math.pi / 2, math.pi, arc_points)
            outer_r = ts - m
            inner_r = m
            return {
                'left': list(zip(cx + outer_r * np.cos(t_outer), cy + outer_r * np.sin(t_outer))),
                'right': list(zip(cx + inner_r * np.cos(t_inner), cy + inner_r * np.sin(t_inner)))
            }
        elif bottom and right:
            # Angolo top-left
            cx, cy = px + ts, py + ts
            t_outer = np.linspace(math.pi, 3 * math.pi / 2, arc_points)
            t_inner = np.linspace(math.pi, 3 * math.pi / 2, arc_points)
            outer_r = ts - m
            inner_r = m
            return {
                'left': list(zip(cx + outer_r * np.cos(t_outer), cy + outer_r * np.sin(t_outer))),
                'right': list(zip(cx + inner_r * np.cos(t_inner), cy + inner_r * np.sin(t_inner)))
            }
        
        return {'left': [], 'right': []}


def create_noodle_path(cells, min_len, max_len, allow_overlap):
    """Genera un percorso serpentinante casuale (algoritmo da noodlePath.pde)."""
    global vsk_global
    rows = len(cells)
    cols = len(cells[0])
    
    length = int(vsk_global.random(min_len, max_len))
    
    # Trova punto di partenza casuale
    attempts = 0
    while attempts < 200:
        sx = int(vsk_global.random(0, cols))
        sy = int(vsk_global.random(0, rows))
        if cells[sy][sx] == EMPTY:
            break
        attempts += 1
    else:
        return None  # Nessun punto libero trovato
    
    path = [Point(sx, sy)]
    cells[sy][sx] = OCCUPIED
    
    # Crea il percorso
    for _ in range(1, length):
        prev = path[-1]
        
        # Trova direzioni disponibili
        directions = []
        
        # Su
        if prev.y > 0:
            if cells[prev.y - 1][prev.x] == EMPTY:
                directions.append(('up', prev.x, prev.y - 1))
            elif allow_overlap and can_cross(cells, prev.x, prev.y, 'up'):
                directions.append(('up', prev.x, prev.y - 1))
        
        # Giù
        if prev.y < rows - 1:
            if cells[prev.y + 1][prev.x] == EMPTY:
                directions.append(('down', prev.x, prev.y + 1))
            elif allow_overlap and can_cross(cells, prev.x, prev.y, 'down'):
                directions.append(('down', prev.x, prev.y + 1))
        
        # Sinistra
        if prev.x > 0:
            if cells[prev.y][prev.x - 1] == EMPTY:
                directions.append(('left', prev.x - 1, prev.y))
            elif allow_overlap and can_cross(cells, prev.x, prev.y, 'left'):
                directions.append(('left', prev.x - 1, prev.y))
        
        # Destra
        if prev.x < cols - 1:
            if cells[prev.y][prev.x + 1] == EMPTY:
                directions.append(('right', prev.x + 1, prev.y))
            elif allow_overlap and can_cross(cells, prev.x, prev.y, 'right'):
                directions.append(('right', prev.x + 1, prev.y))
        
        if not directions:
            break  # Bloccato
        
        # Scegli direzione casuale
        direction, nx, ny = directions[int(vsk_global.random(0, len(directions)))]
        
        # Gestisci incrocio
        if cells[ny][nx] != EMPTY:
            # Incrocio: marca le celle appropriate
            if direction in ['up', 'down']:
                cells[ny][nx] = H_CROSSED
            else:
                cells[ny][nx] = V_CROSSED
        
        new_point = Point(nx, ny)
        path.append(new_point)
        
        if cells[ny][nx] == EMPTY:
            cells[ny][nx] = OCCUPIED
        
        # Marca il tipo di cella per il punto precedente
        if len(path) > 2:
            mark_cell_type(cells, path, len(path) - 2)
    
    if len(path) > 2:
        return path
    else:
        # Percorso troppo corto, libera celle
        for p in path:
            if cells[p.y][p.x] != V_CROSSED and cells[p.y][p.x] != H_CROSSED:
                cells[p.y][p.x] = EMPTY
        return None


def can_cross(cells, x, y, direction):
    """Controlla se può attraversare una cella perpendicolare."""
    rows = len(cells)
    cols = len(cells[0])
    
    if direction == 'up':
        if y >= 2 and cells[y - 1][x] == HORIZONTAL and cells[y - 2][x] == EMPTY:
            return True
    elif direction == 'down':
        if y < rows - 2 and cells[y + 1][x] == HORIZONTAL and cells[y + 2][x] == EMPTY:
            return True
    elif direction == 'left':
        if x >= 2 and cells[y][x - 1] == VERTICAL and cells[y][x - 2] == EMPTY:
            return True
    elif direction == 'right':
        if x < cols - 2 and cells[y][x + 1] == VERTICAL and cells[y][x + 2] == EMPTY:
            return True
    
    return False


def mark_cell_type(cells, path, idx):
    """Marca il tipo di cella (verticale/orizzontale) basato sui vicini."""
    if idx >= 2 and idx < len(path):
        current = path[idx]
        prev = path[idx - 1]
        two_back = path[idx - 2]
        
        if two_back.x == current.x:
            # Movimento verticale
            if cells[prev.y][prev.x] != V_CROSSED and cells[prev.y][prev.x] != H_CROSSED:
                cells[prev.y][prev.x] = VERTICAL
        elif two_back.y == current.y:
            # Movimento orizzontale
            if cells[prev.y][prev.x] != V_CROSSED and cells[prev.y][prev.x] != H_CROSSED:
                cells[prev.y][prev.x] = HORIZONTAL


# Global per vsk.random
vsk_global = None


class SerpentineTubesSketch(vsketch.SketchClass):
    # Parametri
    grid_cols = vsketch.Param(18, 2, step=1)
    grid_rows = vsketch.Param(11, 2, step=1)
    num_noodles = vsketch.Param(3, 1, step=1)
    num_tubes = vsketch.Param(6, 1, step=1)
    tube_thickness = vsketch.Param(0.5, 0.1, 1.0, decimals=2)
    min_length = vsketch.Param(30, 10, step=5)
    max_length = vsketch.Param(150, 20, step=10)
    allow_overlap = vsketch.Param(True)
    
    def draw(self, vsk: vsketch.Vsketch) -> None:
        global vsk_global
        vsk_global = vsk
        
        vsk.size("a4", landscape=True)
        vsk.scale("cm")
        
        cols = int(self.grid_cols)
        rows = int(self.grid_rows)
        n_noodles = int(self.num_noodles)
        n_tubes = int(self.num_tubes)
        thickness = float(self.tube_thickness)
        
        # Calcola tile size per riempire la pagina
        margin = 1.5  # cm
        available_w = 29.7 - 2 * margin
        available_h = 21.0 - 2 * margin
        
        tile_size = min(available_w / cols, available_h / rows)
        
        # Centra la griglia
        total_w = cols * tile_size
        total_h = rows * tile_size
        offset_x = (29.7 - total_w) / 2
        offset_y = (21.0 - total_h) / 2
        
        vsk.translate(offset_x, offset_y)
        
        # Inizializza griglia celle
        cells = [[EMPTY for _ in range(cols)] for _ in range(rows)]
        
        # Genera noodles
        noodles = []
        for i in range(n_noodles):
            path = create_noodle_path(
                cells,
                int(self.min_length),
                int(self.max_length),
                self.allow_overlap
            )
            
            if path:
                noodle = Noodle(path, tile_size, thickness, i + 1)
                noodles.append(noodle)
        
        # Disegna tutti i noodles
        for i, noodle in enumerate(noodles):
            vsk.stroke(i + 1)  # Layer diverso per ogni noodle
            noodle.draw(vsk, n_tubes, self.allow_overlap)
    
    def finalize(self, vsk: vsketch.Vsketch) -> None:
        vsk.vpype("linemerge linesimplify reloop linesort")


if __name__ == "__main__":
    SerpentineTubesSketch.display()
