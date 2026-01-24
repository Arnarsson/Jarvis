# Jarvis Desktop Agent

Privacy-first desktop agent that captures screenshots and uploads them to a Jarvis server for processing.

## Features

- Lightweight screen capture with change detection
- Privacy-first: configurable exclusion rules for sensitive apps
- System tray integration with status indicator
- CLI interface for configuration and control
- Automatic idle detection to pause capture

## Requirements

- Python 3.11+
- Linux (primary) or macOS (secondary)
- Tesseract OCR (for local text extraction)

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/jarvis.git
cd jarvis/agent

# Install in development mode
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

## Usage

```bash
# Show version
jarvis --version

# Show agent status
jarvis status

# More commands coming soon:
# jarvis capture start
# jarvis capture stop
# jarvis config
```

## Configuration

The agent uses environment variables with the `JARVIS_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `JARVIS_CAPTURE_INTERVAL` | 15 | Seconds between captures |
| `JARVIS_IDLE_THRESHOLD` | 300 | Seconds of inactivity before pausing |
| `JARVIS_JPEG_QUALITY` | 80 | JPEG compression quality (1-100) |
| `JARVIS_SERVER_URL` | http://localhost:8000 | Server upload endpoint |
| `JARVIS_LOG_LEVEL` | INFO | Logging level |

## Privacy

Jarvis respects your privacy by default:

- Password managers (1Password, Bitwarden, LastPass, KeePass) are never captured
- Private/incognito browser windows are excluded
- Add your own exclusions for banking apps and sensitive applications

See `~/.config/jarvis/exclusions.yaml` for customization.

## License

MIT
