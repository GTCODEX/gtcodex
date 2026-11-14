#!/usr/bin/env python3
"""Render a 360-degree turntable animation (MP4) from one still photo.

The photo is treated as a flat plane that turns once about its vertical centre
axis under a real perspective camera.  The plane rotation is a projective map,
so every frame is an exact homography of the source pixels (no fake squash):
the near edge grows and the far edge shrinks as the picture turns.

Face-on  -> front of the photo; past 90 degrees the back is shown (mirrored,
the way a print looks when you turn it around).

Usage:
    python tools/spin360.py photo.jpg -o out/spin.mp4
"""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

DEFAULT_SIZE = 1080          # square output, social-ready
DEFAULT_FPS = 30
DEFAULT_SECONDS = 6.0
CAMERA_DISTANCE = 3.0        # in photo-widths; smaller = stronger perspective


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def cover_resize(im: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Scale to fill `size` and centre-crop (CSS `background-size: cover`)."""
    W, H = size
    w, h = im.size
    s = max(W / w, H / h)
    im = im.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
    w, h = im.size
    return im.crop(((w - W) // 2, (h - H) // 2, (w - W) // 2 + W, (h - H) // 2 + H))


def make_backdrop(im: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Heavily blurred, dimmed copy of the photo: a seamless studio backdrop."""
    bg = cover_resize(im, size).filter(ImageFilter.GaussianBlur(45))
    bg = bg.point(lambda v: int(v * 0.32))          # darken
    return bg


def homography(
    src_size: tuple[int, int],
    theta: float,
    out_size: tuple[int, int],
    face_width: int,
    cam_distance: float = CAMERA_DISTANCE,
) -> tuple[np.ndarray, float, float]:
    """Homography mapping source pixels -> output pixels for rotation `theta`.

    Also returns the focal length and the projected y of the bottom edge,
    which the contact shadow needs.
    """
    w, h = src_size
    W, H = out_size
    c, s = math.cos(theta), math.sin(theta)

    # source pixel -> plane coordinates, centred on the rotation axis
    S = np.array([[1.0, 0.0, -w / 2.0],
                  [0.0, 1.0, -h / 2.0],
                  [0.0, 0.0, 1.0]])

    # turn the plane about its vertical axis, then push it away from the camera
    # (X, Y, Z) = (cu*cos, cv, -cu*sin);  Z -= d
    d = cam_distance * w                 # camera distance, in source pixels
    M = np.array([[c, 0.0, 0.0],
                  [0.0, 1.0, 0.0],
                  [-s, 0.0, -d]]) @ S

    f = d * face_width / w               # focal length: face-on width == face_width
    P = np.array([[f, 0.0, 0.0],         # perspective divide by (d - Z)
                  [0.0, f, 0.0],
                  [0.0, 0.0, -1.0]])
    T = np.array([[1.0, 0.0, W / 2.0],
                  [0.0, 1.0, H / 2.0],
                  [0.0, 0.0, 1.0]])
    Hm = T @ P @ M
    bottom_y = H / 2.0 + f * (h / 2.0) / d   # bottom edge, at cu = 0
    return Hm, f, bottom_y


def pil_coeffs(H: np.ndarray) -> tuple[float, ...]:
    """PIL wants the inverse map (output -> source), denominator normalised."""
    Hinv = np.linalg.inv(H)
    Hinv = Hinv / Hinv[2, 2]
    return tuple(Hinv.flatten()[:8])


def draw_shadow(
    size: tuple[int, int], width: float, bottom_y: float, strength: float
) -> Image.Image:
    """Soft elliptical contact shadow under the turning picture."""
    W, H = size
    layer = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(layer)
    rx = max(4.0, width * 0.52)
    ry = max(3.0, width * 0.075)
    cy = min(H - ry - 2, bottom_y + 0.018 * H)
    d.ellipse([W / 2 - rx, cy - ry, W / 2 + rx, cy + ry],
              fill=int(120 * strength))
    return layer.filter(ImageFilter.GaussianBlur(max(8.0, width * 0.045)))


# --------------------------------------------------------------------------
# frame rendering
# --------------------------------------------------------------------------
def render_frame(
    front: Image.Image,
    back: Image.Image,
    backdrop: Image.Image,
    theta: float,
    face_width: int,
    out_size: tuple[int, int],
    shadow: bool,
) -> Image.Image:
    W, H = out_size
    c = math.cos(theta)
    frame = backdrop.copy()

    if abs(c) < 0.02:
        return frame                      # perfectly edge-on: nothing to show

    Hm, f, bottom_y = homography(front.size, theta, out_size, face_width)
    coeffs = pil_coeffs(Hm)
    src = front if c >= 0 else back

    # the plane, projected
    warped = src.transform((W, H), Image.PERSPECTIVE, coeffs, Image.BICUBIC)
    mask = Image.new("L", src.size, 255).transform(
        (W, H), Image.PERSPECTIVE, coeffs, Image.BICUBIC
    )

    # a turning surface catches less light as it edges away from the camera
    shade = 0.42 + 0.58 * abs(c) ** 0.7
    if shade < 1.0:
        warped = warped.point(lambda v: int(v * shade))

    if shadow:
        frame.paste(
            (0, 0, 0),
            (0, 0),
            draw_shadow(out_size, face_width * abs(c), bottom_y, 0.9),
        )

    frame.paste(warped, (0, 0), mask)
    return frame


def encode(frames, out_path: Path, fps: int, size: tuple[int, int]) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            raise SystemExit("ffmpeg not found (pip install imageio-ffmpeg)")

    cmd = [
        ffmpeg, "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{size[0]}x{size[1]}", "-r", str(fps), "-i", "-",
        "-an",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for fr in frames:
        proc.stdin.write(fr.tobytes())
    proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "replace")
    if proc.wait() != 0:
        raise SystemExit("ffmpeg failed:\n" + err[-2000:])


# --------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="+", type=Path)
    ap.add_argument("-o", "--outdir", type=Path, default=Path("out"))
    ap.add_argument("--size", type=int, default=DEFAULT_SIZE,
                    help="square output resolution (default 1080)")
    ap.add_argument("--fps", type=int, default=DEFAULT_FPS)
    ap.add_argument("--seconds", type=float, default=DEFAULT_SECONDS,
                    help="duration of one full revolution")
    ap.add_argument("--fill", type=float, default=0.74,
                    help="face-on width as a fraction of the frame")
    ap.add_argument("--no-shadow", action="store_true")
    args = ap.parse_args(argv)

    out_size = (args.size, args.size)
    args.outdir.mkdir(parents=True, exist_ok=True)

    for path in args.images:
        im = Image.open(path).convert("RGB")
        backdrop = make_backdrop(im, out_size)

        # fit the picture inside the frame, keeping its aspect ratio
        w, h = im.size
        face_width = int(args.size * args.fill)
        face_height = int(face_width * h / w)
        if face_height > int(args.size * args.fill * 1.45):
            face_height = int(args.size * args.fill * 1.45)
            face_width = int(face_height * w / h)
        front = im.resize((face_width, face_height), Image.LANCZOS)
        back = front.transpose(Image.FLIP_LEFT_RIGHT)

        n = max(1, round(args.seconds * args.fps))
        out_path = args.outdir / f"{path.stem}_360.mp4"
        print(f"{path.name}: {n} frames -> {out_path}")

        def gen():
            for i in range(n):
                theta = 2 * math.pi * i / n
                yield render_frame(front, back, backdrop, theta,
                                   face_width, out_size, not args.no_shadow)

        encode(gen(), out_path, args.fps, out_size)
        print(f"  wrote {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
