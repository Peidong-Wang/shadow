# Shadow App Icons

This directory should contain app icons for different platforms. Icons can be generated using the Tauri CLI:

```bash
cd ../..
npm run tauri icon /path/to/icon.png
```

Or manually:

1. Create a 1024x1024 PNG icon (`icon.png`) in this directory
2. Run the tauri icon command from the project root:

```bash
npm run tauri icon icons/icon.png
```

This will automatically generate all required sizes for:

- macOS: `icon.icns`
- Windows: `icon.ico`
- Linux: `32x32.png`, `128x128.png`, `128x128@2x.png`

## Icon Requirements

- Format: PNG with transparent background
- Minimum size: 1024x1024 pixels
- Should be a simple, recognizable symbol of "Shadow" concept (e.g., a dark silhouette, eye, or abstract agent icon)

Placeholder icon files will be auto-generated during build if not present.
