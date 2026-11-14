"""Validate + shrink uploaded photos so pages stay fast on plant-floor phones."""
import uuid
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 12 * 1024 * 1024
ALLOWED = {"JPEG", "PNG", "WEBP"}


class ImageRejected(ValueError):
    """Message is safe to show to the admin."""


def optimize_image(uploaded, max_side=1600, quality=85):
    if uploaded.size > MAX_BYTES:
        raise ImageRejected("Image is larger than 12 MB — please use a smaller photo.")
    try:
        img = Image.open(uploaded)
        fmt = img.format
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ImageRejected("This file is not a valid image. Please upload a JPG, PNG or WEBP photo.")
    if fmt not in ALLOWED:
        raise ImageRejected("Please upload a JPG, PNG or WEBP photo.")
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    else:
        img = img.convert("RGB")
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
    return ContentFile(buf.getvalue(), name=f"{uuid.uuid4().hex}.jpg")
