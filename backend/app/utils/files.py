"""
File upload utilities
"""
import os
import uuid
from fastapi import UploadFile, HTTPException
from ..config import settings


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx"}


def get_file_extension(filename: str) -> str:
    """Get file extension from filename"""
    if not filename:
        return ""
    return os.path.splitext(filename)[1].lower()


def validate_image_file(file: UploadFile) -> None:
    """Validate that file is an allowed image type"""
    ext = get_file_extension(file.filename)
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}",
        )


def validate_file_size(file: UploadFile, max_size_mb: int = None) -> None:
    """Validate file size"""
    max_size = (max_size_mb or settings.MAX_FILE_SIZE_MB) * 1024 * 1024

    # Read file to check size
    file.file.seek(0, 2)  # Seek to end
    size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    if size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {max_size_mb or settings.MAX_FILE_SIZE_MB}MB",
        )


def save_upload_file(
    file: UploadFile,
    directory: str,
    filename: str = None,
    validate_image: bool = True,
) -> str:
    """
    Save an uploaded file to the specified directory.

    Args:
        file: The uploaded file
        directory: Subdirectory within UPLOAD_DIR
        filename: Optional custom filename (without extension)
        validate_image: Whether to validate as image file

    Returns:
        Relative path to saved file
    """
    if validate_image:
        validate_image_file(file)

    validate_file_size(file)

    # Generate filename
    ext = get_file_extension(file.filename)
    if not filename:
        filename = str(uuid.uuid4())
    final_filename = f"{filename}{ext}"

    # Create directory
    full_dir = os.path.join(settings.UPLOAD_DIR, directory)
    os.makedirs(full_dir, exist_ok=True)

    # Save file
    file_path = os.path.join(full_dir, final_filename)
    with open(file_path, "wb") as f:
        content = file.file.read()
        f.write(content)

    # Return relative path
    return os.path.join(directory, final_filename)


def delete_file(relative_path: str) -> bool:
    """
    Delete a file from the upload directory.

    Args:
        relative_path: Path relative to UPLOAD_DIR

    Returns:
        True if file was deleted, False if it didn't exist
    """
    full_path = os.path.join(settings.UPLOAD_DIR, relative_path)
    if os.path.exists(full_path):
        os.remove(full_path)
        return True
    return False
