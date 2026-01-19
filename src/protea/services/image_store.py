"""Image storage service for protea."""

import base64
import io
import logging
import shutil
from pathlib import Path
from typing import TypedDict

from PIL import Image

logger = logging.getLogger("protea")


class ImageMetadata(TypedDict):
    """Metadata returned when saving an image."""

    file_path: str
    thumbnail_path: str
    width: int
    height: int
    file_size_bytes: int


class ImageStore:
    """Manages image storage with thumbnails and WebP conversion."""

    def __init__(
        self,
        base_path: Path,
        image_format: str = "webp",
        quality: int = 85,
        thumbnail_size: tuple[int, int] = (200, 200),
    ):
        """Initialize image store.

        Args:
            base_path: Base directory for image storage
            image_format: Output format (default: webp)
            quality: JPEG/WebP quality (1-100)
            thumbnail_size: Max dimensions for thumbnails
        """
        self.base_path = Path(base_path)
        self.image_format = image_format.lower()
        self.quality = quality
        self.thumbnail_size = thumbnail_size

        # Ensure directories exist
        (self.base_path / "bins").mkdir(parents=True, exist_ok=True)
        (self.base_path / "sessions").mkdir(parents=True, exist_ok=True)

    def _get_format_for_save(self) -> str:
        """Get PIL format string for saving."""
        format_map = {
            "webp": "WEBP",
            "jpg": "JPEG",
            "jpeg": "JPEG",
            "png": "PNG",
        }
        return format_map.get(self.image_format, "WEBP")

    def save_session_image(
        self,
        session_id: str,
        image_base64: str,
        image_id: str,
        original_filename: str | None = None,
    ) -> ImageMetadata:
        """Save image to session directory.

        Args:
            session_id: Session UUID
            image_base64: Base64-encoded image data
            image_id: UUID for the image
            original_filename: Original filename (for logging)

        Returns:
            ImageMetadata with paths and dimensions
        """
        session_dir = self.base_path / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # Decode and process image
        image_bytes = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(image_bytes))

        # Convert to RGB if necessary (for JPEG/WebP)
        if img.mode in ("RGBA", "P") and self.image_format in ("webp", "jpg", "jpeg"):
            img = img.convert("RGB")

        # Save main image
        file_path = session_dir / f"{image_id}.{self.image_format}"
        img.save(
            file_path,
            format=self._get_format_for_save(),
            quality=self.quality,
        )

        # Create thumbnail
        thumb = img.copy()
        thumb.thumbnail(self.thumbnail_size)
        thumbnail_path = session_dir / f"{image_id}_thumb.{self.image_format}"
        thumb.save(
            thumbnail_path,
            format=self._get_format_for_save(),
            quality=self.quality,
        )

        logger.debug(f"Saved session image {image_id} from {original_filename}")

        return ImageMetadata(
            file_path=str(file_path.relative_to(self.base_path)),
            thumbnail_path=str(thumbnail_path.relative_to(self.base_path)),
            width=img.width,
            height=img.height,
            file_size_bytes=file_path.stat().st_size,
        )

    def save_bin_image(
        self,
        bin_id: str,
        image_base64: str,
        image_id: str,
    ) -> ImageMetadata:
        """Save image directly to bin directory.

        Args:
            bin_id: Bin UUID
            image_base64: Base64-encoded image data
            image_id: UUID for the image

        Returns:
            ImageMetadata with paths and dimensions
        """
        bin_dir = self.base_path / "bins" / bin_id
        bin_dir.mkdir(parents=True, exist_ok=True)

        # Decode and process image
        image_bytes = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(image_bytes))

        # Convert to RGB if necessary
        if img.mode in ("RGBA", "P") and self.image_format in ("webp", "jpg", "jpeg"):
            img = img.convert("RGB")

        # Save main image
        file_path = bin_dir / f"{image_id}.{self.image_format}"
        img.save(
            file_path,
            format=self._get_format_for_save(),
            quality=self.quality,
        )

        # Create thumbnail
        thumb = img.copy()
        thumb.thumbnail(self.thumbnail_size)
        thumbnail_path = bin_dir / f"{image_id}_thumb.{self.image_format}"
        thumb.save(
            thumbnail_path,
            format=self._get_format_for_save(),
            quality=self.quality,
        )

        return ImageMetadata(
            file_path=str(file_path.relative_to(self.base_path)),
            thumbnail_path=str(thumbnail_path.relative_to(self.base_path)),
            width=img.width,
            height=img.height,
            file_size_bytes=file_path.stat().st_size,
        )

    def copy_to_bin(
        self,
        session_image_path: str,
        bin_id: str,
        new_image_id: str,
    ) -> ImageMetadata:
        """Copy session image to bin directory.

        Args:
            session_image_path: Relative path to session image
            bin_id: Target bin UUID
            new_image_id: UUID for the new bin image

        Returns:
            ImageMetadata with new paths
        """
        bin_dir = self.base_path / "bins" / bin_id
        bin_dir.mkdir(parents=True, exist_ok=True)

        # Copy main image
        src_path = self.base_path / session_image_path
        dst_path = bin_dir / f"{new_image_id}.{self.image_format}"

        img = Image.open(src_path)
        img.save(
            dst_path,
            format=self._get_format_for_save(),
            quality=self.quality,
        )

        # Copy/create thumbnail
        src_thumb = src_path.parent / f"{src_path.stem}_thumb{src_path.suffix}"
        dst_thumb = bin_dir / f"{new_image_id}_thumb.{self.image_format}"

        if src_thumb.exists():
            thumb = Image.open(src_thumb)
        else:
            thumb = img.copy()
            thumb.thumbnail(self.thumbnail_size)

        thumb.save(
            dst_thumb,
            format=self._get_format_for_save(),
            quality=self.quality,
        )

        return ImageMetadata(
            file_path=str(dst_path.relative_to(self.base_path)),
            thumbnail_path=str(dst_thumb.relative_to(self.base_path)),
            width=img.width,
            height=img.height,
            file_size_bytes=dst_path.stat().st_size,
        )

    def delete_image(self, file_path: str) -> bool:
        """Delete an image and its thumbnail.

        Args:
            file_path: Relative path to the image

        Returns:
            True if deleted, False if not found
        """
        full_path = self.base_path / file_path
        if full_path.exists():
            full_path.unlink()

            # Try to delete thumbnail
            thumb_path = full_path.parent / f"{full_path.stem}_thumb{full_path.suffix}"
            if thumb_path.exists():
                thumb_path.unlink()

            logger.debug(f"Deleted image {file_path}")
            return True

        return False

    def delete_session_images(self, session_id: str) -> int:
        """Delete all images for a session.

        Args:
            session_id: Session UUID

        Returns:
            Number of images deleted
        """
        session_dir = self.base_path / "sessions" / session_id
        if session_dir.exists():
            # Count image files (not thumbnails)
            count = len(
                [f for f in session_dir.iterdir() if not f.stem.endswith("_thumb")]
            )
            shutil.rmtree(session_dir)
            logger.debug(f"Deleted {count} session images for session {session_id}")
            return count
        return 0

    def get_absolute_path(self, relative_path: str) -> Path:
        """Get absolute path for an image.

        Args:
            relative_path: Path relative to base_path

        Returns:
            Absolute Path object
        """
        return self.base_path / relative_path

    def get_image_as_base64(self, relative_path: str) -> str | None:
        """Read an image and return as base64.

        Args:
            relative_path: Path relative to base_path

        Returns:
            Base64-encoded image data, or None if not found
        """
        full_path = self.base_path / relative_path
        if full_path.exists():
            with open(full_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        return None
