"""Draws the application's icon: `uv run python packaging/make_icon.py` writes Mathessible.icns and .ico."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from PIL import Image

HERE = Path(__file__).parent


def picture(path: Path) -> None:
    figure = plt.figure(figsize=(4, 4), dpi=256)
    axes = figure.add_axes([0, 0, 1, 1])
    axes.set_xlim(0, 1)
    axes.set_ylim(0, 1)
    axes.axis("off")
    box = FancyBboxPatch((0.09, 0.09), 0.82, 0.82, boxstyle="round,pad=0,rounding_size=0.18", color="#0063D6")
    axes.add_patch(box)
    axes.text(0.5, 0.49, r"$\sqrt{x}$", color="white", fontsize=118, ha="center", va="center")
    figure.savefig(path, transparent=True)
    plt.close(figure)


if __name__ == "__main__":
    source = HERE / "icon.png"
    picture(source)
    image = Image.open(source)
    image.save(HERE / "Mathessible.icns")
    image.save(HERE / "Mathessible.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    source.unlink()
