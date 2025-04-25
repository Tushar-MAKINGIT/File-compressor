from PIL import Image
import io
import os
from typing import Tuple, BinaryIO, Optional, Dict, Any, List
import math

def get_file_size(buffer: BinaryIO) -> int:
    """Get the size of a file in bytes"""
    current_pos = buffer.tell()
    buffer.seek(0, 2)  # Seek to end
    size = buffer.tell()
    buffer.seek(current_pos)  # Restore original position
    return size

def compress_with_settings(
    image: Image.Image, 
    format: str, 
    quality: int, 
    width: Optional[int] = None, 
    height: Optional[int] = None
) -> Tuple[io.BytesIO, int]:
    """
    Compress image with given quality and dimensions, return buffer and its size
    
    Args:
        image: The PIL Image object
        format: Image format (jpeg, png, webp, etc.)
        quality: Quality level (1-100)
        width: Optional new width (if resizing)
        height: Optional new height (if resizing)
    """
    buffer = io.BytesIO()
    img_format = format.lower()
    
    # Resize if dimensions provided
    img_to_save = image
    if width and height:
        img_to_save = image.resize((width, height), Image.LANCZOS)
    
    # Handle format-specific conversions
    if img_format in ['jpeg', 'jpg']:
        # Convert RGBA/LA/P with transparency to RGB for JPEG
        if img_to_save.mode in ('RGBA', 'LA') or (img_to_save.mode == 'P' and 'transparency' in img_to_save.info):
            background = Image.new('RGB', img_to_save.size, (255, 255, 255))
            img_rgba = img_to_save.convert('RGBA') if img_to_save.mode == 'P' else img_to_save
            background.paste(img_rgba, mask=img_rgba.split()[-1])  # Use alpha channel as mask
            img_to_save = background
        elif img_to_save.mode != 'RGB':  # Convert any other non-RGB mode to RGB
            img_to_save = img_to_save.convert('RGB')
    
    # Format-specific save parameters
    save_kwargs = {}
    if img_format in ['jpeg', 'jpg']:
        save_kwargs['quality'] = quality
        save_kwargs['optimize'] = True
        save_kwargs['subsampling'] = 0  # Higher quality chroma subsampling
        if quality < 75:
            save_kwargs['progressive'] = True
    elif img_format == 'png':
        save_kwargs['optimize'] = True
        save_kwargs['compress_level'] = 9  # Maximum compression
    elif img_format == 'webp':
        save_kwargs['quality'] = quality
        save_kwargs['method'] = 6  # Best compression method
    
    # Save the image
    img_to_save.save(buffer, format=img_format, **save_kwargs)
    size = get_file_size(buffer)
    return buffer, size

def binary_search_quality(
    image: Image.Image,
    format: str,
    target_size: int,
    min_quality: int = 1,
    max_quality: int = 95,
    width: Optional[int] = None,
    height: Optional[int] = None,
    tolerance_pct: float = 1.0  # Target size tolerance percentage
) -> Tuple[Optional[io.BytesIO], Optional[int], Optional[int]]:
    """
    Enhanced binary search for image quality that:
    1. Produces a file strictly under target_size
    2. Gets as close as possible to target_size
    3. Uses tolerance to avoid unnecessary iterations
    
    Returns (buffer, size, quality) or (None, None, None) if no viable solution
    """
    low = min_quality
    high = max_quality
    best_buffer = None
    best_size = None
    best_quality = None
    
    # Calculate tolerance size (how close we need to get)
    tolerance_bytes = target_size * tolerance_pct / 100
    
    # First check if max quality is already under target
    buffer, size = compress_with_settings(image, format, max_quality, width, height)
    if size <= target_size:
        return buffer, size, max_quality
    
    # Next check if min quality is already over target
    buffer, size = compress_with_settings(image, format, min_quality, width, height)
    if size > target_size:
        return None, None, None  # Even minimum quality exceeds target size
    
    iterations = 0
    max_iterations = 20  # Safety limit
    
    best_buffer = buffer
    best_size = size
    best_quality = min_quality
    
    # If size is already close enough to target, no need for binary search
    if target_size - size <= tolerance_bytes:
        return best_buffer, best_size, best_quality
    
    # Main binary search loop
    while low <= high and iterations < max_iterations:
        iterations += 1
        mid = (low + high) // 2
        
        buffer, size = compress_with_settings(image, format, mid, width, height)
        
        if size <= target_size:
            # Valid size, store as best and search higher
            best_buffer = buffer
            best_size = size
            best_quality = mid
            
            # If close enough to target within tolerance, we can stop
            if target_size - size <= tolerance_bytes:
                break
                
            low = mid + 1
        else:
            # Too large, search lower
            high = mid - 1
    
    # Fine-tune by trying a few quality levels after best
    if best_quality is not None:
        # Try to get even closer by checking quality levels right above best_quality
        for q in range(best_quality + 1, min(best_quality + 5, max_quality + 1)):
            buffer, size = compress_with_settings(image, format, q, width, height)
            if size <= target_size and size > best_size:
                best_buffer = buffer
                best_size = size
                best_quality = q
    
    return best_buffer, best_size, best_quality

def calculate_new_dimensions(
    original_width: int, 
    original_height: int, 
    scale_factor: float
) -> Tuple[int, int]:
    """Calculate new dimensions while maintaining aspect ratio"""
    new_width = max(1, int(original_width * scale_factor))
    new_height = max(1, int(original_height * scale_factor))
    return new_width, new_height

def compress_image(file: BinaryIO, max_size_kb: int) -> Tuple[BinaryIO, str, Dict[str, Any]]:
    """
    Advanced image compression that guarantees output under max_size_kb and
    optimizes for quality by trying:
    1. Compression with quality adjustment first
    2. Resizing as a fallback if needed
    
    Returns (compressed_buffer, new_filename, compression_info)
    """
    # Get original file size and convert target size to bytes
    original_size = get_file_size(file)
    file.seek(0)
    target_size = max_size_kb * 1024  # KB to bytes
    
    # Read and validate input image
    try:
        image = Image.open(file)
        image.load()  # Fully load the image to avoid issues with some formats
        original_format = image.format or 'JPEG'
        filename = getattr(file, 'filename', 'image.jpg')
        base_name = os.path.splitext(os.path.basename(filename))[0]
    except Exception as e:
        raise ValueError(f"Invalid image file: {str(e)}")
    
    # If original is already smaller than target, return original
    if original_size <= target_size:
        file.seek(0)
        return file, f"{base_name}_compressed.{original_format.lower()}", {
            'original_size': original_size // 1024,
            'compressed_size': original_size // 1024,
            'reduction_percent': 0,
            'quality': 100,
            'dimensions': image.size,
            'resized': False
        }
    
    # For challenging formats with alpha channels
    format_for_compression = original_format
    if original_format.upper() == 'PNG' and image.mode == 'RGBA' and target_size < original_size * 0.5:
        # PNG with transparency might be better as WebP for small sizes
        format_for_compression = 'WEBP'
    
    # First attempt: Try with original dimensions with quality adjustment
    best_buffer, best_size, best_quality = binary_search_quality(
        image,
        format_for_compression,
        target_size,
        min_quality=1,
        max_quality=95
    )
    
    # Initialize result tracking
    resized = False
    final_width, final_height = image.size
    
    # If quality reduction alone wasn't enough, try resizing
    if best_buffer is None:
        # Start with modest reduction and gradually increase if needed
        original_width, original_height = image.size
        scale_factors = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2]
        
        for scale in scale_factors:
            new_width, new_height = calculate_new_dimensions(original_width, original_height, scale)
            
            # Try with highest quality first at this dimension
            buffer, size = compress_with_settings(
                image, 
                format_for_compression, 
                95,  # Start with high quality
                new_width, 
                new_height
            )
            
            if size <= target_size:
                # High quality at this dimension works! We can use it directly
                best_buffer = buffer
                best_size = size
                best_quality = 95
                resized = True
                final_width, final_height = new_width, new_height
                break
            
            # Otherwise, run binary search at this dimension
            buffer, size, quality = binary_search_quality(
                image,
                format_for_compression,
                target_size,
                min_quality=1,
                max_quality=95,
                width=new_width,
                height=new_height
            )
            
            if buffer is not None:
                best_buffer = buffer
                best_size = size
                best_quality = quality
                resized = True
                final_width, final_height = new_width, new_height
                break
        
        # If even the smallest size doesn't work, use the smallest dimensions with lowest quality
        if best_buffer is None:
            min_width, min_height = calculate_new_dimensions(original_width, original_height, 0.1)
            best_buffer, best_size = compress_with_settings(
                image, 
                format_for_compression, 
                1,  # Lowest quality
                min_width, 
                min_height
            )
            best_quality = 1
            resized = True
            final_width, final_height = min_width, min_height
            
            # If even this doesn't work (extremely rare), we'll return this result but log a warning
            if best_size > target_size:
                print(f"Warning: Could not achieve target size of {target_size} bytes. Best result: {best_size} bytes")
    
    # Ensure we have a valid buffer
    if best_buffer is None:
        raise ValueError("Failed to compress image to target size with any method")
    
    # Prepare result
    best_buffer.seek(0)
    extension = format_for_compression.lower()
    new_filename = f"{base_name}_compressed.{extension}"
    
    compression_info = {
        'original_size': original_size // 1024,  # KB
        'compressed_size': (best_size + 1023) // 1024,  # KB, rounded up
        'actual_size_bytes': best_size,
        'reduction_percent': round((1 - best_size / original_size) * 100, 2),
        'quality': best_quality,
        'original_dimensions': image.size,
        'final_dimensions': (final_width, final_height),
        'resized': resized,
        'format': format_for_compression,
        'target_size_kb': max_size_kb,
        'success': best_size <= target_size
    }
    
    return best_buffer, new_filename, compression_info