"""Create the framed diagonal README comparison image."""

import sys
from PIL import Image, ImageDraw

def process_and_composite(dark_path, light_path, output_comp_path, border_color=(180, 180, 180, 255), border_width=2):
    """Create a framed diagonal light/dark composite.

    DWM shadow margins are detected from the Dark image and the same crop is
    applied to both inputs. ``border_width`` is measured in output pixels.

    Args:
        dark_path: Raw Dark theme PNG.
        light_path: Raw Light theme PNG with dimensions matching ``dark_path``.
        output_comp_path: Destination for the comparison PNG.
        border_color: RGBA border color applied to the generated image.
        border_width: Border thickness in pixels.

    Returns:
        The generated comparison-image path.
    """
    img_dark = Image.open(dark_path).convert("RGBA")
    img_light = Image.open(light_path).convert("RGBA")

    if img_dark.size != img_light.size:
        raise ValueError(f"Image dimensions do not match: Dark is {img_dark.size}, Light is {img_light.size}")

    w_orig, h_orig = img_dark.size

    # Auto-detect content bounds by scanning every pixel so narrow DWM shadows (< 10px on
    # Windows 11) are not skipped. The threshold of 20 distinguishes near-black shadow
    # pixels from actual window content.
    pixels = img_dark.load()

    left = 0
    for x in range(w_orig):
        if any(pixels[x, y][0] > 20 or pixels[x, y][1] > 20 or pixels[x, y][2] > 20 for y in range(h_orig)):
            left = x
            break

    right = w_orig - 1
    for x in range(w_orig - 1, -1, -1):
        if any(pixels[x, y][0] > 20 or pixels[x, y][1] > 20 or pixels[x, y][2] > 20 for y in range(h_orig)):
            right = x
            break

    top = 0
    for y in range(h_orig):
        if any(pixels[x, y][0] > 20 or pixels[x, y][1] > 20 or pixels[x, y][2] > 20 for x in range(w_orig)):
            top = y
            break

    bottom = h_orig - 1
    for y in range(h_orig - 1, -1, -1):
        if any(pixels[x, y][0] > 20 or pixels[x, y][1] > 20 or pixels[x, y][2] > 20 for x in range(w_orig)):
            bottom = y
            break

    crop_box = (left, top, right + 1, bottom + 1)

    # A margin larger than 30px suggests the input was already framed or pre-cropped,
    # which would cause the shadow scan to eat into real window content on the next run.
    right_margin = w_orig - right - 1
    bottom_margin = h_orig - bottom - 1
    if left > 30 or top > 30 or right_margin > 30 or bottom_margin > 30:
        print(f"Warning: unusually large shadow margins detected "
              f"(left={left}, top={top}, right={right_margin}, bottom={bottom_margin}). "
              "Input images may already be cropped or framed.")

    print(f"Content crop box (stripping DWM shadow): {crop_box}")

    dark_crop = img_dark.crop(crop_box)
    light_crop = img_light.crop(crop_box)

    W, H = dark_crop.size

    # Add the configured pixel border to individual dark and light images.
    def apply_frame(img):
        framed = img.copy()
        draw = ImageDraw.Draw(framed)
        for i in range(border_width):
            draw.rectangle([i, i, W - 1 - i, H - 1 - i], outline=border_color)
        return framed

    dark_framed = apply_frame(dark_crop)
    light_framed = apply_frame(light_crop)

    # Composite along '\' diagonal. The 16%/86% split is chosen so the dividing line
    # clears the WinUtil tab bar on the left and the action buttons on the right,
    # keeping both UI regions fully visible in their respective theme half.
    top_x = 0.16 * W
    bot_x = 0.86 * W

    scale = 4
    MW, MH = W * scale, H * scale

    poly = [
        (0, 0),
        (top_x * scale, 0),
        (bot_x * scale, MH),
        (0, MH)
    ]

    mask_high = Image.new("L", (MW, MH), 0)
    draw_mask = ImageDraw.Draw(mask_high)
    draw_mask.polygon(poly, fill=255)

    # Downsample mask with LANCZOS for smooth anti-aliased edge
    mask = mask_high.resize((W, H), resample=Image.Resampling.LANCZOS)
    composite = Image.composite(light_framed, dark_framed, mask)

    # Re-apply outer border frame to composite image
    draw_comp = ImageDraw.Draw(composite)
    for i in range(border_width):
        draw_comp.rectangle([i, i, W - 1 - i, H - 1 - i], outline=border_color)

    composite.save(output_comp_path, "PNG")
    print(f"Successfully generated final diagonal composite: {output_comp_path} ({W}x{H})")
    return output_comp_path

if __name__ == "__main__":
    dark = sys.argv[1] if len(sys.argv) > 1 else "winutil-dark.png"
    light = sys.argv[2] if len(sys.argv) > 2 else "winutil-light.png"
    out = sys.argv[3] if len(sys.argv) > 3 else "winutil-light-dark-comparison.png"
    process_and_composite(dark, light, out)
