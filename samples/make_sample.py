"""Write samples/sample.jpg: three synthetic skin-tone patches under side light.

Synthetic on purpose: a demo photo with no real person in it needs no consent or
licence, and visitors can try the app without uploading a picture of themselves.
Deterministic (fixed seed), so rerunning reproduces the same image.
"""
from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parent / "sample.jpg"
HEIGHT, WIDTH = 1200, 1600
BACKDROP = (86, 96, 112)  # slate
PATCHES = [(330, 600, (238, 214, 196)), (800, 600, (184, 132, 102)), (1270, 600, (74, 52, 42))]
RADII = (230, 330)
NOISE_SIGMA = 6  # camera-like sensor noise
SEED = 1


def main() -> None:
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)
    img = np.empty((HEIGHT, WIDTH, 3), np.float32)
    img[:] = BACKDROP
    for cx, cy, rgb in PATCHES:
        inside = ((xx - cx) / RADII[0]) ** 2 + ((yy - cy) / RADII[1]) ** 2 <= 1
        shade = (1.0 - 0.18 * ((xx - cx) / RADII[0]) ** 2)[..., None]  # rounded falloff
        img[inside] = (np.array(rgb, np.float32) * shade)[inside]
    img *= (0.78 + 0.32 * (1 - xx / WIDTH))[..., None]  # window light from the left
    img += np.random.default_rng(SEED).normal(0, NOISE_SIGMA, img.shape)
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(OUT, quality=88)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
