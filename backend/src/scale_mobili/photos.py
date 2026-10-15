import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

from scale_mobili.domain import DomainError


def sanitize_photo(body):
    if len(body) > 5 * 1024 * 1024:
        raise DomainError("Foto oltre il limite di 5 MB", 413)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(body)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("Formato non supportato")
                if image.width * image.height > 20_000_000:
                    raise ValueError("Foto oltre 20 megapixel")
                if getattr(image, "n_frames", 1) != 1:
                    raise ValueError("Immagini animate non supportate")
                image.load()
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((1200, 1200))
                clean = Image.new("RGB", image.size)
                clean.paste(image)
                output = io.BytesIO()
                clean.save(output, format="JPEG", quality=82, optimize=True)
                if output.tell() > 1024 * 1024:
                    raise ValueError("Foto ricodificata troppo grande")
                return output.getvalue(), clean.width, clean.height
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise DomainError("Foto non valida: usare JPEG, PNG o WebP, massimo 20 megapixel") from exc
