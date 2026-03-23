# MS Paint / Beyond All Reason renderer

This folder now supports two vector output modes in `main.py`:

- `RENDER_MODE = 'paint'`: the original MS Paint mouse-drag playback.
- `RENDER_MODE = 'bar'`: writes Beyond All Reason skuttle spawn commands into `bar-commands/frameXXXX.txt`.

## Beyond All Reason mode

The BAR mode uses the same contour-based outline approach as the MS Paint version, but samples extra points along each contour segment and emits one command per sampled point:

```text
/give 1 corsktl 2 @x,10,y
```

Important tuning variables in `main.py`:

- `BAR_POINT_SPACING`: minimum distance between sampled contour points. Increase this for faster testing at lower resolution.
- `BAR_MARGIN`: keeps the image away from the edge of the map.
- `BAR_OFFSET_X` / `BAR_OFFSET_Y`: shifts the entire drawing on the map.
- `FRAME_STEP`: skips frames for faster experiments.
- `BAR_MAP_WIDTH` / `BAR_MAP_HEIGHT`: target map dimensions.

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
