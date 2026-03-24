from pathlib import Path

import cv2

# Input video frames
BASE_PNG_DIR = 'pngs'
BASE_PNG_PATH = BASE_PNG_DIR + '/png%d.png'
FRAMES = 4383
FRAME_STEP = 3

# BAR display resolution (simple pixel-grid approach)
DISPLAY_WIDTH = 256
DISPLAY_HEIGHT = 256

# BAR map mapping
BAR_MAP_WIDTH = 12000
BAR_MAP_HEIGHT = 12000
BAR_MARGIN = 300
BAR_OFFSET_X = 0
BAR_OFFSET_Y = 0
BAR_Y = 10
BAR_TEAM = 2
BAR_UNIT = 'corsktl'
BAR_COMMAND_PREFIX = ''  # '' -> "give", '/' -> "/give"

# Frame extraction / thresholding
PIXEL_THRESHOLD = 0  # if resized pixel > 0, emit a unit
INTERPOLATION = cv2.INTER_AREA
PIXEL_SOURCE_MODE = 'edges'  # 'edges' or 'binary'
CANNY_THRESHOLD_1 = 80
CANNY_THRESHOLD_2 = 180
EDGE_RESIZE_INTERPOLATION = cv2.INTER_NEAREST

# Widget output / pacing
BAR_OUTPUT_DIR = Path('bar-commands')
BAR_WIDGET_OUTPUT_PATH = BAR_OUTPUT_DIR / 'cmd_bad_apple_pixels.lua'
BAR_WIDGET_COMMANDS_PER_TICK = 12
BAR_WIDGET_FRAME_GAP = 1
BAR_WIDGET_CLEAR_WAIT_FRAMES = 12

# Debug preview outputs (for tuning thresholds/resolution)
DEBUG_SAVE_PREVIEW_PNGS = True
DEBUG_PREVIEW_DIR = BAR_OUTPUT_DIR / 'debug-previews'
DEBUG_VIDEO_OUTPUT_PATH = BAR_OUTPUT_DIR / 'debug-previews.mp4'
DEBUG_VIDEO_FPS = max(1, int(round(24 / FRAME_STEP)))


def escape_lua_string(value):
    return value.replace('\\', '\\\\').replace('"', '\\"')


def pixel_to_bar(px, py):
    usable_width = BAR_MAP_WIDTH - 2 * BAR_MARGIN
    usable_height = BAR_MAP_HEIGHT - 2 * BAR_MARGIN

    map_x = BAR_MARGIN + (px / max(1, DISPLAY_WIDTH - 1)) * usable_width + BAR_OFFSET_X
    map_y = BAR_MARGIN + (py / max(1, DISPLAY_HEIGHT - 1)) * usable_height + BAR_OFFSET_Y
    return int(round(map_x)), int(round(map_y))


def build_preview_image(resized, source_mask):
    resized_bgr = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)
    mask_img = (source_mask.astype('uint8')) * 255
    mask_bgr = cv2.cvtColor(mask_img, cv2.COLOR_GRAY2BGR)
    return cv2.hconcat([resized_bgr, mask_bgr])


def write_preview_video(preview_paths):
    if not preview_paths:
        return

    first = cv2.imread(str(preview_paths[0]))
    if first is None:
        print(f'warning: could not read first preview image: {preview_paths[0]}')
        return

    height, width = first.shape[:2]
    writer = cv2.VideoWriter(
        str(DEBUG_VIDEO_OUTPUT_PATH),
        cv2.VideoWriter_fourcc(*'mp4v'),
        DEBUG_VIDEO_FPS,
        (width, height)
    )
    if not writer.isOpened():
        print(f'warning: could not open video writer for {DEBUG_VIDEO_OUTPUT_PATH}')
        return

    written = 0
    for path in preview_paths:
        image = cv2.imread(str(path))
        if image is None:
            continue
        if image.shape[0] != height or image.shape[1] != width:
            image = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
        writer.write(image)
        written += 1

    writer.release()
    print(f'wrote {DEBUG_VIDEO_OUTPUT_PATH} ({written} frames @ {DEBUG_VIDEO_FPS} fps)')


def build_frame_commands(frame):
    image = cv2.imread(BASE_PNG_PATH % (frame + 1), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f'Could not read frame image: {BASE_PNG_PATH % (frame + 1)}')

    if PIXEL_SOURCE_MODE == 'edges':
        # Detect edges at the source resolution first, then scale the edge mask down.
        edges_full = cv2.Canny(image, CANNY_THRESHOLD_1, CANNY_THRESHOLD_2)
        source_mask = cv2.resize(
            edges_full,
            (DISPLAY_WIDTH, DISPLAY_HEIGHT),
            interpolation=EDGE_RESIZE_INTERPOLATION
        ) > 0
        resized = cv2.resize(image, (DISPLAY_WIDTH, DISPLAY_HEIGHT), interpolation=INTERPOLATION)
    elif PIXEL_SOURCE_MODE == 'binary':
        resized = cv2.resize(image, (DISPLAY_WIDTH, DISPLAY_HEIGHT), interpolation=INTERPOLATION)
        source_mask = resized > PIXEL_THRESHOLD
    else:
        raise ValueError(f'Unknown PIXEL_SOURCE_MODE: {PIXEL_SOURCE_MODE}')

    commands = []
    for y in range(DISPLAY_HEIGHT):
        for x in range(DISPLAY_WIDTH):
            is_on = bool(source_mask[y, x])
            if is_on:
                map_x, map_y = pixel_to_bar(x, y)
                commands.append(f'{BAR_COMMAND_PREFIX}give 1 {BAR_UNIT} {BAR_TEAM} @{map_x},{BAR_Y},{map_y}')

    return commands, resized, source_mask


def write_pixel_widget():
    BAR_OUTPUT_DIR.mkdir(exist_ok=True)
    if DEBUG_SAVE_PREVIEW_PNGS:
        DEBUG_PREVIEW_DIR.mkdir(exist_ok=True)

    frames = []
    preview_paths = []
    total_rendered = 0
    for frame in range(0, FRAMES, FRAME_STEP):
        commands, resized, source_mask = build_frame_commands(frame)
        if commands:
            frames.append((frame + 1, commands))
            total_rendered += len(commands)
        print(f'frame {frame + 1}: edge-commands={len(commands)}')

        if DEBUG_SAVE_PREVIEW_PNGS:
            preview_image = build_preview_image(resized, source_mask)
            preview_path = DEBUG_PREVIEW_DIR / f'frame{frame + 1:04d}.png'
            cv2.imwrite(str(preview_path), preview_image)
            preview_paths.append(preview_path)

    lines = [
        '-- Auto-generated by ms-paint/bar_pixel_widget.py',
        '-- Simple pixel mode: resize each frame and spawn one unit per non-zero pixel.',
        '',
        'function widget:GetInfo()',
        '  return {',
        '    name = "BadApplePixelRunner",',
        '    desc = "Plays rasterized pixel frames using give commands",',
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
        '  Spring.Echo("BadApplePixelRunner loaded: " .. tostring(#frameOrder) .. " frames")',
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
    print(
        f'wrote {BAR_WIDGET_OUTPUT_PATH} ({len(frames)} frames, {total_commands} commands, '
        f'total_rendered={total_rendered})'
    )

    if DEBUG_SAVE_PREVIEW_PNGS:
        write_preview_video(preview_paths)


if __name__ == '__main__':
    write_pixel_widget()
