"""Profile-photo processing: validate, fix phone rotation, centre-crop to a square, shrink, save as JPEG."""
import uuid
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 5 * 1024 * 1024
ALLOWED = {"JPEG", "PNG", "WEBP"}
SIZE = 320


class AvatarError(ValueError):
    pass


def process_avatar(uploaded):
    """Return a ContentFile (square JPEG, 320px) for an uploaded image or raise AvatarError."""
    if uploaded.size > MAX_BYTES:
        raise AvatarError("big")
    try:
        img = Image.open(uploaded)
        fmt = img.format
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise AvatarError("type")
    if fmt not in ALLOWED:
        raise AvatarError("type")
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[3])
        img = bg
    else:
        img = img.convert("RGB")
    img = ImageOps.fit(img, (SIZE, SIZE), Image.LANCZOS, centering=(0.5, 0.4))  # bias up: faces sit high
    buf = BytesIO()
    img.save(buf, "JPEG", quality=86, optimize=True)
    return ContentFile(buf.getvalue(), name=f"{uuid.uuid4().hex}.jpg")
