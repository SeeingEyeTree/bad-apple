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
FRAMES = 4383
FPS = 24

BASE_PNG_DIR = 'pngs'
BASE_PNG_PATH = BASE_PNG_DIR + '/png%d.png'

# Rendering mode:
# - 'paint': original mouse-drag approach.
# - 'bar': writes one txt command file per frame.
# - 'bar_widget': writes a Lua widget that executes generated commands in-game.
RENDER_MODE = 'bar_widget'
FRAME_STEP = 3

# Beyond All Reason / Full Metal Plate tuning.
BAR_MAP_WIDTH = 12000
BAR_MAP_HEIGHT = 12000
BAR_TEAM = 2
BAR_UNIT = 'corsktl'
BAR_Y = 10
BAR_OUTPUT_DIR = Path('bar-commands')
BAR_POINT_SPACING = 280
BAR_POINT_SPACING_MODE = 'map'  # 'map' units or 'frame' pixels
BAR_MARGIN = 300
BAR_COMMAND_PREFIX = ''  # '' -> "give ...", '/' -> "/give ..."
BAR_WIDGET_OUTPUT_PATH = Path('bar-commands') / 'cmd_bad_apple.lua'
BAR_WIDGET_COMMANDS_PER_TICK = 12
BAR_WIDGET_FRAME_GAP = 1
BAR_WIDGET_CLEAR_WAIT_FRAMES = 12

# Per-map offsets can be adjusted if you want to shift the whole video.
BAR_OFFSET_X = 0
BAR_OFFSET_Y = 0

# Optional canvas override (for "draw inside this rectangle" workflows).
# Coordinates can be in either order; mapping uses min/max per axis.
BAR_CANVAS_TOP_LEFT = (1857, 1377)
BAR_CANVAS_BOTTOM_RIGHT = (509, 45)
BAR_USE_CANVAS_BOUNDS = False

# Optional simplification before point sampling.
CONTOUR_APPROX_EPSILON = 0.0
BINARY_THRESHOLD = 100
CONTOUR_CHAIN_MODE = cv2.CHAIN_APPROX_NONE
SAMPLING_METHOD = 'uniform_arclength'  # 'uniform_arclength' or 'segment_steps'

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
    contours, _ = cv2.findContours(binary, cv2.RETR_TREE, CONTOUR_CHAIN_MODE)
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


def to_world_delta(dx_px, dy_px):
    if BAR_USE_CANVAS_BOUNDS:
        min_x = min(BAR_CANVAS_TOP_LEFT[0], BAR_CANVAS_BOTTOM_RIGHT[0])
        max_x = max(BAR_CANVAS_TOP_LEFT[0], BAR_CANVAS_BOTTOM_RIGHT[0])
        min_y = min(BAR_CANVAS_TOP_LEFT[1], BAR_CANVAS_BOTTOM_RIGHT[1])
        max_y = max(BAR_CANVAS_TOP_LEFT[1], BAR_CANVAS_BOTTOM_RIGHT[1])
        usable_width = max_x - min_x
        usable_height = max_y - min_y
    else:
        usable_width = BAR_MAP_WIDTH - 2 * BAR_MARGIN
        usable_height = BAR_MAP_HEIGHT - 2 * BAR_MARGIN

    scale_x = usable_width / max(1, WIDTH - 1)
    scale_y = usable_height / max(1, HEIGHT - 1)
    return dx_px * scale_x, dy_px * scale_y


def resolve_frame_spacing():
    if BAR_POINT_SPACING_MODE == 'frame':
        return max(0.1, BAR_POINT_SPACING)
    if BAR_POINT_SPACING_MODE == 'map':
        dx_world, _ = to_world_delta(1, 0)
        _, dy_world = to_world_delta(0, 1)
        px_scale = max(0.001, (abs(dx_world) + abs(dy_world)) / 2.0)
        return max(0.1, BAR_POINT_SPACING / px_scale)
    raise ValueError(f'Unknown BAR_POINT_SPACING_MODE: {BAR_POINT_SPACING_MODE}')


def sample_closed_polyline_uniform(points, spacing):
    if len(points) < 2:
        return points

    chain = points + [points[0]]
    segments = []
    total_length = 0.0
    for i in range(len(chain) - 1):
        ax, ay = chain[i]
        bx, by = chain[i + 1]
        length = math.hypot(bx - ax, by - ay)
        if length == 0:
            continue
        segments.append((ax, ay, bx, by, length))
        total_length += length

    if total_length == 0:
        return [points[0]]

    sample_count = max(3, int(math.ceil(total_length / spacing)))
    step = total_length / sample_count

    sampled = []
    target_distance = 0.0
    seg_idx = 0
    seg_progress = 0.0

    for _ in range(sample_count):
        while seg_idx < len(segments):
            ax, ay, bx, by, seg_length = segments[seg_idx]
            remaining = seg_length - seg_progress
            if target_distance <= remaining:
                t = (seg_progress + target_distance) / seg_length
                x = int(round(ax + (bx - ax) * t))
                y = int(round(ay + (by - ay) * t))
                point = (x, y)
                if not sampled or sampled[-1] != point:
                    sampled.append(point)
                seg_progress += target_distance
                target_distance = step
                break
            target_distance -= remaining
            seg_idx += 1
            seg_progress = 0.0
        if seg_idx >= len(segments):
            break

    return sampled


def iter_sampled_contour_points(contour, spacing):
    points = simplify_contour(contour)
    if not points:
        return

    if SAMPLING_METHOD == 'uniform_arclength':
        for sampled_point in sample_closed_polyline_uniform(points, spacing):
            yield sampled_point
        return

    if SAMPLING_METHOD == 'segment_steps':
        prev = points[0]
        yield prev
        for point in points[1:] + [points[0]]:
            for sampled_point in sample_line_points(prev, point, spacing)[1:]:
                yield sampled_point
            prev = point
        return

    raise ValueError(f'Unknown SAMPLING_METHOD: {SAMPLING_METHOD}')


def frame_to_bar(point):
    x, y = point

    if BAR_USE_CANVAS_BOUNDS:
        min_x = min(BAR_CANVAS_TOP_LEFT[0], BAR_CANVAS_BOTTOM_RIGHT[0])
        max_x = max(BAR_CANVAS_TOP_LEFT[0], BAR_CANVAS_BOTTOM_RIGHT[0])
        min_y = min(BAR_CANVAS_TOP_LEFT[1], BAR_CANVAS_BOTTOM_RIGHT[1])
        max_y = max(BAR_CANVAS_TOP_LEFT[1], BAR_CANVAS_BOTTOM_RIGHT[1])

        map_x = min_x + (x / max(1, WIDTH - 1)) * (max_x - min_x) + BAR_OFFSET_X
        map_y = min_y + (y / max(1, HEIGHT - 1)) * (max_y - min_y) + BAR_OFFSET_Y
    else:
        usable_width = BAR_MAP_WIDTH - 2 * BAR_MARGIN
        usable_height = BAR_MAP_HEIGHT - 2 * BAR_MARGIN
        map_x = BAR_MARGIN + (x / max(1, WIDTH - 1)) * usable_width + BAR_OFFSET_X
        map_y = BAR_MARGIN + (y / max(1, HEIGHT - 1)) * usable_height + BAR_OFFSET_Y

    return int(round(map_x)), int(round(map_y))


def dedupe_consecutive(points):
    deduped = []
    for point in points:
        if not deduped or deduped[-1] != point:
            deduped.append(point)
    return deduped


def build_frame_commands(frame):
    frame_spacing = resolve_frame_spacing()
    commands = []

    for contour in load_contours(frame):
        contour_points = [frame_to_bar(point) for point in iter_sampled_contour_points(contour, frame_spacing)]
        for map_x, map_y in dedupe_consecutive(contour_points):
            commands.append(f'{BAR_COMMAND_PREFIX}give 1 {BAR_UNIT} {BAR_TEAM} @{map_x},{BAR_Y},{map_y}')
    return commands


def write_bar_frame(frame):
    BAR_OUTPUT_DIR.mkdir(exist_ok=True)
    commands = [
        f'; frame {frame + 1}',
        '; clear suggestion: box select -> self d -> CTRL+B',
    ]
    frame_commands = build_frame_commands(frame)
    commands.extend(frame_commands)

    output_path = BAR_OUTPUT_DIR / f'frame{frame + 1:04d}.txt'
    output_path.write_text('\n'.join(commands) + '\n', encoding='utf-8')
    print(f'wrote {output_path} ({len(frame_commands)} placements)')


def escape_lua_string(value):
    return value.replace('\\', '\\\\').replace('"', '\\"')


def write_bar_widget():
    BAR_OUTPUT_DIR.mkdir(exist_ok=True)

    frames = []
    for frame in range(0, FRAMES, FRAME_STEP):
        commands = build_frame_commands(frame)
        if commands:
            frames.append((frame + 1, commands))

    lines = [
        '-- Auto-generated by ms-paint/main.py',
        '-- clear suggestion per frame: box select -> self d -> CTRL+B',
        '',
        'function widget:GetInfo()',
        '  return {',
        '    name = "BadAppleCommandRunner",',
        '    desc = "Plays generated /give commands for Bad Apple outlines",',
        '    author = "bad-apple script",',
        '    layer = 0,',
        '    enabled = true',
        '  }',
        'end',
        '',
        f'local COMMANDS_PER_TICK = {BAR_WIDGET_COMMANDS_PER_TICK}',
        f'local FRAME_GAP = {BAR_WIDGET_FRAME_GAP}',
        f'local CLEAR_WAIT_FRAMES = {BAR_WIDGET_CLEAR_WAIT_FRAMES}',
        f'local TARGET_TEAM = {BAR_TEAM}',
        'local frames = {'
    ]

    for frame_number, commands in frames:
        escaped = ', '.join(f'"{escape_lua_string(command)}"' for command in commands)
        lines.append(f'  [{frame_number}] = {{{escaped}}},')

    lines.extend([
        '}',
        'local frameOrder = {'
    ])

    for frame_number, _ in frames:
        lines.append(f'  {frame_number},')

    lines.extend([
        '}',
        '',
        'local frameIndex = 1',
        'local commandIndex = 1',
        'local gapCounter = 0',
        'local clearWaitCounter = 0',
        'local clearedFrame = false',
        '',
        'local function selfDestructTeamUnits(teamID)',
        '  local units = Spring.GetAllUnits()',
        '  for i = 1, #units do',
        '    local unitID = units[i]',
        '    if Spring.GetUnitTeam(unitID) == teamID then',
        '      Spring.GiveOrderToUnit(unitID, CMD.SELFD, {}, 0)',
        '    end',
        '  end',
        'end',
        '',
        'function widget:Initialize()',
        '  Spring.Echo("BadAppleCommandRunner loaded: " .. tostring(#frameOrder) .. " frames")',
        'end',
        '',
        'function widget:GameFrame()',
        '  if gapCounter > 0 then',
        '    gapCounter = gapCounter - 1',
        '    return',
        '  end',
        '',
        '  local frameNumber = frameOrder[frameIndex]',
        '  if frameNumber == nil then',
        '    return',
        '  end',
        '',
        '  local commands = frames[frameNumber]',
        '',
        '  if not clearedFrame then',
        '    selfDestructTeamUnits(TARGET_TEAM)',
        '    clearWaitCounter = CLEAR_WAIT_FRAMES',
        '    clearedFrame = true',
        '    return',
        '  end',
        '',
        '  if clearWaitCounter > 0 then',
        '    clearWaitCounter = clearWaitCounter - 1',
        '    return',
        '  end',
        '',
        '  local sent = 0',
        '  while commandIndex <= #commands and sent < COMMANDS_PER_TICK do',
        '    Spring.SendCommands(commands[commandIndex])',
        '    commandIndex = commandIndex + 1',
        '    sent = sent + 1',
        '  end',
        '',
        '  if commandIndex > #commands then',
        '    frameIndex = frameIndex + 1',
        '    commandIndex = 1',
        '    gapCounter = FRAME_GAP',
        '    clearedFrame = false',
        '  end',
        'end',
        ''
    ])

    BAR_WIDGET_OUTPUT_PATH.write_text('\n'.join(lines), encoding='utf-8')
    total_commands = sum(len(commands) for _, commands in frames)
    print(f'wrote {BAR_WIDGET_OUTPUT_PATH} ({len(frames)} frames, {total_commands} commands)')


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
    elif RENDER_MODE == 'bar_widget':
        write_bar_widget()
    else:
        raise ValueError(f'Unknown render mode: {RENDER_MODE}')


if __name__ == '__main__':
    if RENDER_MODE == 'paint':
        time.sleep(15)
        select_brush()
        for i in range(0, FRAMES, FRAME_STEP):
            render_frame(i)
    elif RENDER_MODE == 'bar':
        for i in range(0, FRAMES, FRAME_STEP):
            render_frame(i)
    elif RENDER_MODE == 'bar_widget':
        write_bar_widget()
    else:
        raise ValueError(f'Unknown render mode: {RENDER_MODE}')
