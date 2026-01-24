"""Icon generation utilities for system tray status indicators."""

from enum import Enum

from PIL import Image, ImageDraw

__all__ = [
    "TrayStatus",
    "STATUS_COLORS",
    "create_status_icon",
    "create_icon_with_indicator",
]


class TrayStatus(Enum):
    """System tray status states."""

    ACTIVE = "active"  # Green - capturing
    PAUSED = "paused"  # Yellow - user paused
    IDLE = "idle"  # Yellow - auto-paused due to idle
    EXCLUDED = "excluded"  # Yellow - excluded app active
    ERROR = "error"  # Red - error state
    SYNCING = "syncing"  # Blue - uploading


# Material Design color palette for status indicators
# RGB tuples for PIL compatibility
STATUS_COLORS: dict[TrayStatus, tuple[int, int, int]] = {
    TrayStatus.ACTIVE: (76, 175, 80),  # Material green 500
    TrayStatus.PAUSED: (255, 193, 7),  # Material amber 500
    TrayStatus.IDLE: (255, 193, 7),  # Same as paused
    TrayStatus.EXCLUDED: (255, 193, 7),  # Same as paused
    TrayStatus.ERROR: (244, 67, 54),  # Material red 500
    TrayStatus.SYNCING: (33, 150, 243),  # Material blue 500
}


def create_status_icon(status: TrayStatus, size: int = 64) -> Image.Image:
    """Create a circular status icon.

    Creates a filled circle with the status color on a transparent background.
    Includes a subtle dark border for visibility on both light and dark themes.

    Args:
        status: The tray status to create an icon for.
        size: The size of the icon in pixels (width and height).

    Returns:
        A PIL Image with RGBA mode.
    """
    # Create transparent background
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Get color for status
    color = STATUS_COLORS[status]

    # Calculate circle dimensions with padding for border
    padding = max(2, size // 16)  # Scale padding with size
    border_width = max(1, size // 32)  # Subtle border

    # Draw outer border (dark, semi-transparent for depth)
    border_color = (40, 40, 40, 180)  # Dark gray, semi-transparent
    draw.ellipse(
        [padding, padding, size - padding - 1, size - padding - 1],
        fill=border_color,
    )

    # Draw main circle (slightly smaller to show border)
    inner_padding = padding + border_width
    draw.ellipse(
        [inner_padding, inner_padding, size - inner_padding - 1, size - inner_padding - 1],
        fill=(*color, 255),  # Full opacity
    )

    # Add subtle highlight for 3D effect (light arc at top)
    highlight_padding = inner_padding + max(1, size // 16)
    highlight_size = size // 3
    highlight_color = (255, 255, 255, 60)  # Very subtle white
    draw.arc(
        [
            highlight_padding,
            highlight_padding,
            highlight_padding + highlight_size,
            highlight_padding + highlight_size,
        ],
        start=200,
        end=340,
        fill=highlight_color,
        width=max(1, size // 32),
    )

    return img


def create_icon_with_indicator(
    status: TrayStatus,
    base_icon: Image.Image | None = None,
    size: int = 64,
) -> Image.Image:
    """Create an icon with a status indicator.

    If a base icon is provided, overlays a small status dot in the bottom-right corner.
    Otherwise, creates a simple status circle icon.

    Args:
        status: The tray status for the indicator.
        base_icon: Optional base icon to overlay the indicator on.
        size: The size of the final icon in pixels.

    Returns:
        A PIL Image with RGBA mode.
    """
    if base_icon is None:
        # No base icon - return simple status circle
        return create_status_icon(status, size)

    # Resize base icon to target size if needed
    if base_icon.size != (size, size):
        base_icon = base_icon.resize((size, size), Image.Resampling.LANCZOS)

    # Ensure RGBA mode for compositing
    if base_icon.mode != "RGBA":
        base_icon = base_icon.convert("RGBA")

    # Create a copy to avoid modifying original
    result = base_icon.copy()

    # Create small status indicator (1/3 of icon size)
    indicator_size = size // 3
    indicator = create_status_icon(status, indicator_size)

    # Position in bottom-right corner with small margin
    margin = size // 16
    position = (size - indicator_size - margin, size - indicator_size - margin)

    # Composite indicator onto base
    result.paste(indicator, position, indicator)

    return result
