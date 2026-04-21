# sounds/

Place your alert sound files (`.wav` or `.ogg`) in this directory.

## Generating a default beep

Run the helper script from the project root to create a simple `alert.wav`:

```
python generate_default_sound.py
```

This produces a short 440 Hz beep that you can use as the default alert.

## Recommended formats

| Format | Notes                                   |
|--------|-----------------------------------------|
| `.wav` | Best compatibility, no extra codec needed |
| `.ogg` | Smaller files; supported by pygame       |
| `.mp3` | Supported when pygame includes mp3 codec |

Set the sound file for each monitor in **Edit Monitor → Sound File**.
