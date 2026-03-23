import math
import time
from pathlib import Path

import cv2
import pyautogui as gui

# method used is vector, ignore raster methods

const_x = 10

colours = {
    'black': (882, 68),
    'grey': (912, 68)
}

WIDTH = 480
HEIGHT = 360
FRAMES = 5258
FPS = 24

BASE_PNG_DIR = 'frames'
BASE_PNG_PATH = BASE_PNG_DIR + '/frame%d.png'

# Rendering mode: 'paint' uses the original mouse-drag approach,
# 'bar' writes Beyond All Reason skuttle-spawn commands instead.
RENDER_MODE = 'bar'
FRAME_STEP = 3

# Beyond All Reason / Full Metal Plate tuning.
BAR_MAP_WIDTH = 12000
BAR_MAP_HEIGHT = 12000
BAR_TEAM = 2
BAR_UNIT = 'corsktl'
BAR_Y = 10
BAR_OUTPUT_DIR = Path('bar-commands')
BAR_POINT_SPACING = 24
BAR_MARGIN = 300

# Per-map offsets can be adjusted if you want to shift the whole video.
BAR_OFFSET_X = 0
BAR_OFFSET_Y = 0

# Optional simplification before point sampling.
CONTOUR_APPROX_EPSILON = 1.25
BINARY_THRESHOLD = 100

gui.PAUSE = 0.000000000001


def select_colour(colour, position):
    gui.click(colours[colour][0], colours[colour][1])
    time.sleep(0.01)
    gui.doubleClick()
    if position is not None:
        gui.moveTo(position[0], position[1])


def select_brush():
    gui.click(400, 70)
    time.sleep(0.01)
    gui.doubleClick()


def select_bucket():  # selects fill tool (unused)
    gui.click(305, 75)
    time.sleep(0.01)
    gui.doubleClick()


def draw_row(row, prev, y, code):  # draws row as raster
    gui.moveTo(const_x, y)
    skip = False
    for i, elem in enumerate(row + [3]):
        if elem == prev[i] and skip:
            continue

        elif elem != prev[i] and skip:
            gui.moveTo(i * 20, y)
            skip = False
            continue

        elif (i > 0 and row[i - 1] != elem) or elem == prev[i]:
            if elem == prev[i]:
                skip = True
            if code == 1 and row[i - 1] == 0:
                gui.dragTo(i * 20, y, button='right')
            elif row[i - 1] == code:
                gui.dragTo(i * 20, y)
            else:
                gui.moveTo(i * 20, y)


def draw_matrix(matrix, prev):  # raster method
    select_colour('black', gui.position())
    for y, row in enumerate(matrix):
        if (prev is None or row != prev[y]) and 1 in row:
            draw_row(row, [4] * (WIDTH + 1) if prev is None else prev[y] + [4], y * 20 + 180, 1)
    select_colour('grey', gui.position())
    for y, row in enumerate(matrix):
        if (prev is None or row != prev[y]) and 2 in row:
            draw_row(row, [4] * (WIDTH + 1) if prev is None else prev[y] + [4], y * 20 + 180, 2)


def load_contours(frame):
    img = cv2.imread(BASE_PNG_PATH % (frame + 1), 0)
    _, binary = cv2.threshold(img, BINARY_THRESHOLD, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    return contours


def simplify_contour(contour):
    if CONTOUR_APPROX_EPSILON <= 0:
        return [tuple(point[0]) for point in contour.tolist()]
    approx = cv2.approxPolyDP(contour, CONTOUR_APPROX_EPSILON, True)
    return [tuple(point[0]) for point in approx.tolist()]


def sample_line_points(start, end, spacing):
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        return [start]

    steps = max(1, int(math.ceil(length / spacing)))
    points = []
    for step in range(steps + 1):
        ratio = step / steps
        x = int(round(x1 + dx * ratio))
        y = int(round(y1 + dy * ratio))
        point = (x, y)
        if not points or points[-1] != point:
            points.append(point)
    return points


def iter_sampled_contour_points(contour, spacing):
    points = simplify_contour(contour)
    if not points:
        return

    prev = points[0]
    yield prev
    for point in points[1:] + [points[0]]:
        for sampled_point in sample_line_points(prev, point, spacing)[1:]:
            yield sampled_point
        prev = point


def frame_to_bar(point):
    usable_width = BAR_MAP_WIDTH - 2 * BAR_MARGIN
    usable_height = BAR_MAP_HEIGHT - 2 * BAR_MARGIN

    x, y = point
    map_x = BAR_MARGIN + (x / max(1, WIDTH - 1)) * usable_width + BAR_OFFSET_X
    map_y = BAR_MARGIN + (y / max(1, HEIGHT - 1)) * usable_height + BAR_OFFSET_Y
    return int(round(map_x)), int(round(map_y))


def dedupe_consecutive(points):
    deduped = []
    for point in points:
        if not deduped or deduped[-1] != point:
            deduped.append(point)
    return deduped


def write_bar_frame(frame):
    BAR_OUTPUT_DIR.mkdir(exist_ok=True)
    commands = [
        f'; frame {frame + 1}',
        '; clear suggestion: box select -> self d -> CTRL+B',
    ]

    placed_points = []
    for contour in load_contours(frame):
        contour_points = [frame_to_bar(point) for point in iter_sampled_contour_points(contour, BAR_POINT_SPACING)]
        for map_x, map_y in dedupe_consecutive(contour_points):
            commands.append(f'/give 1 {BAR_UNIT} {BAR_TEAM} @{map_x},{BAR_Y},{map_y}')
            placed_points.append((map_x, map_y))

    output_path = BAR_OUTPUT_DIR / f'frame{frame + 1:04d}.txt'
    output_path.write_text('\n'.join(commands) + '\n', encoding='utf-8')
    print(f'wrote {output_path} ({len(placed_points)} placements)')


def draw_vectors(frame):  # vector method
    contours = load_contours(frame)

    for contour in contours:
        lst = contour.tolist()
        begin = lst[0][0]
        gui.moveTo(begin[0] * 2 + 15, begin[1] * 2 + 180)
        for i in range(1, len(lst)):
            point = lst[i][0]
            gui.dragTo(point[0] * 2 + 15, point[1] * 2 + 180)
        gui.dragTo(begin[0] * 2 + 15, begin[1] * 2 + 180)

    time.sleep(1)

    gui.hotkey('ctrl', 'a')
    gui.press('del')
    select_brush()


def render_frame(frame):
    if RENDER_MODE == 'paint':
        draw_vectors(frame)
    elif RENDER_MODE == 'bar':
        write_bar_frame(frame)
    else:
        raise ValueError(f'Unknown render mode: {RENDER_MODE}')


if __name__ == '__main__':
    if RENDER_MODE == 'paint':
        time.sleep(15)
        select_brush()

    for i in range(0, FRAMES, FRAME_STEP):
        render_frame(i)
