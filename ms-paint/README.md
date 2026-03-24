# MS Paint / Beyond All Reason renderer

This folder now supports two vector output modes in `main.py`:

- `RENDER_MODE = 'paint'`: the original MS Paint mouse-drag playback.
- `RENDER_MODE = 'bar'`: writes Beyond All Reason skuttle spawn commands into `bar-commands/frameXXXX.txt`.
- `RENDER_MODE = 'bar_widget'`: writes a Lua widget (`bar-commands/cmd_bad_apple.lua`) that can execute generated commands in-game over time.

## Beyond All Reason mode

The BAR mode uses the same contour-based outline approach as the MS Paint version, but samples extra points along each contour segment and emits one command per sampled point:

```text
/give 1 corsktl 2 @x,10,y
```

Important tuning variables in `main.py`:

- `BAR_POINT_SPACING`: minimum distance between sampled contour points. Increase this for faster testing at lower resolution.
- `BAR_MARGIN`: keeps the image away from the edge of the map.
- `BAR_OFFSET_X` / `BAR_OFFSET_Y`: shifts the entire drawing on the map.
- `BAR_WIDGET_COMMANDS_PER_TICK`: how many `/give` commands the generated widget runs per game tick.
- `BAR_WIDGET_FRAME_GAP`: game ticks to wait between frame transitions in the generated widget.
- `BAR_WIDGET_CLEAR_WAIT_FRAMES`: game frames to wait after self-destruct and before spawning the next frame.
- `FRAME_STEP`: skips frames for faster experiments.
- `BAR_MAP_WIDTH` / `BAR_MAP_HEIGHT`: target map dimensions.
- `BAR_CANVAS_TOP_LEFT` / `BAR_CANVAS_BOTTOM_RIGHT`: optional explicit canvas corners.
- `BAR_USE_CANVAS_BOUNDS`: set `True` to use those canvas corners instead of map width/height + margin scaling.

The generated frame files also include a reminder comment for your current manual clear flow:

```text
; clear suggestion: box select -> self d -> CTRL+B
```

## Running

From this directory:

```bash
python main.py
```

When `RENDER_MODE = 'bar'`, the script writes command files and does not use mouse automation.

When `RENDER_MODE = 'bar_widget'`, copy `bar-commands/cmd_bad_apple.lua` into your BAR widgets folder and load it in-game.

The generated widget now does a per-frame clear pass:
- calls `Spring.GetAllUnits()`
- self-destructs only units on team `BAR_TEAM` (default team 2)
- waits `BAR_WIDGET_CLEAR_WAIT_FRAMES`
- then starts issuing `/give` commands for the new frame
