import os
import uuid
import subprocess
import logging
from typing import Tuple, Optional, Dict
import json

# Buffer range in MB
BUFFER_MIN = 1.0  # Minimum difference from max size
BUFFER_MAX = 2.0  # Maximum difference from max size
BUFFER_AVG = (BUFFER_MIN + BUFFER_MAX) / 2

def get_video_info(video_path: str) -> Tuple[float, int, int, str]:
    """
    Get video duration, width, height, and format using ffprobe.
    Returns: (duration_seconds, width, height, format)
    """
    try:
        # Get all video information in one call with more detailed output
        info_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration,format_name:stream=width,height,codec_name,codec_type",
            "-select_streams", "v:0",  # Select first video stream
            "-of", "json",
            video_path
        ]
        info_result = subprocess.run(info_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if info_result.returncode != 0:
            error_msg = info_result.stderr.strip()
            logging.error(f"FFprobe error: {error_msg}")
            raise RuntimeError(f"Failed to get video info: {error_msg}")
            
        info = json.loads(info_result.stdout)
        
        # Extract information with better error handling
        try:
            duration = float(info['format']['duration'])
            format_name = info['format']['format_name'].split(',')[0]  # Get primary format
            
            # Find video stream with better error handling
            if 'streams' not in info or not info['streams']:
                raise ValueError("No streams found in video file")
                
            video_stream = next((s for s in info['streams'] if s.get('codec_type') == 'video'), None)
            if not video_stream:
                raise ValueError("No video stream found in file")
                
            width = int(video_stream['width'])
            height = int(video_stream['height'])
            
            return duration, width, height, format_name
            
        except KeyError as e:
            logging.error(f"Missing key in video info: {str(e)}")
            raise ValueError(f"Could not read video information: Missing {str(e)}")
            
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse FFprobe output: {str(e)}")
        raise ValueError(f"Could not parse video information: {str(e)}")
    except Exception as e:
        logging.error(f"Error getting video info: {str(e)}")
        raise ValueError(f"Could not read video information: {str(e)}")

def run_ffmpeg_compression(
    input_path: str, 
    output_path: str, 
    video_bitrate: int, 
    audio_bitrate: int = 128000,
    width: Optional[int] = None, 
    height: Optional[int] = None,
    format: Optional[str] = None
) -> None:
    """
    Compress video using FFmpeg with specified bitrates and optional dimensions.
    """
    try:
        # Calculate buffer size as a fraction of the video bitrate
        # Use a more conservative approach to stay within FFmpeg's limits
        buffer_size = min(int(video_bitrate * 1.5), 2000000)  # Max 2M buffer size

        # Base command
        command = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-b:v", str(int(video_bitrate)),
            "-b:a", str(int(audio_bitrate)),
            "-bufsize", str(buffer_size),
            "-maxrate", str(int(video_bitrate * 1.2)),  # More conservative maxrate
            "-preset", "fast",
            "-movflags", "+faststart",
            "-loglevel", "error"
        ]
        
        # Add scaling if dimensions are provided
        if width and height:
            command.extend(["-vf", f"scale={width}:{height}"])
            
        # Add output path with format if specified
        if format:
            output_path = f"{os.path.splitext(output_path)[0]}.{format}"
        command.append(output_path)
        
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if result.returncode != 0:
            error_message = result.stderr.decode('utf-8')
            logging.error(f"FFmpeg compression failed: {error_message}")
            raise RuntimeError(f"Video compression failed: {error_message}")
            
    except Exception as e:
        logging.error(f"Error during FFmpeg compression: {str(e)}")
        raise RuntimeError(f"Video compression failed: {str(e)}")

def compress_video_to_target(input_path: str, max_size_mb: float, processed_folder: str = 'compressed') -> Tuple[str, float]:
    """
    Compress video so the final size is 0.3–0.5 MB below the given max_size_mb.
    
    Args:
        input_path: Path to the input video file
        max_size_mb: Target maximum size in MB
        processed_folder: Folder to store the compressed video
        
    Returns:
        tuple: (compressed_file_path, final_file_size_in_MB)
    """
    try:
        # Create processed folder if it doesn't exist
        os.makedirs(processed_folder, exist_ok=True)
        
        # Get video information
        duration, width, height, format = get_video_info(input_path)
        if duration <= 0:
            raise ValueError("Invalid video duration")

        # Define target size to be 0.3-0.5 MB less than max_size_mb
        target_size_mb = max_size_mb - BUFFER_AVG  # Start with average buffer
        min_size_mb = max_size_mb - BUFFER_MAX  # Minimum allowed size
        max_size_mb = max_size_mb - BUFFER_MIN  # Maximum allowed size

        # Convert to bytes
        target_bytes = target_size_mb * 1024 * 1024
        min_bytes = min_size_mb * 1024 * 1024
        max_bytes = max_size_mb * 1024 * 1024

        # Calculate initial video bitrate (in bits per second)
        # Reserve 20% of bitrate for audio
        audio_bitrate = 128000  # 128 kbps for audio
        video_bitrate = ((target_bytes * 8) / duration) - audio_bitrate

        # Ensure video bitrate is within reasonable limits
        min_bitrate = 100000  # 100 kbps minimum
        max_bitrate = 4000000  # 4 Mbps maximum (reduced from 8Mbps)
        video_bitrate = max(min_bitrate, min(video_bitrate, max_bitrate))

        # Output file path
        output_filename = f"{uuid.uuid4().hex}.{format}"
        output_path = os.path.join(processed_folder, output_filename)

        # Initial compression
        run_ffmpeg_compression(input_path, output_path, video_bitrate, audio_bitrate, format=format)
        final_size = os.path.getsize(output_path)

        # If initial compression is too large, try reducing resolution
        if final_size > max_bytes:
            # Calculate new dimensions while maintaining aspect ratio
            scale_factor = 0.8  # Start with 80% of original size
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            
            # Try compression with reduced resolution
            run_ffmpeg_compression(input_path, output_path, video_bitrate, audio_bitrate, 
                                 new_width, new_height, format)
            final_size = os.path.getsize(output_path)

        # Adjust bitrate if result is not in buffer range
        max_attempts = 4
        attempt = 1
        while not (min_bytes <= final_size <= max_bytes) and attempt <= max_attempts:
            if final_size > max_bytes:
                video_bitrate *= 0.9  # Reduce bitrate if too big
            else:
                video_bitrate *= 1.1  # Increase bitrate if too small

            # Ensure bitrate stays within limits
            video_bitrate = max(min_bitrate, min(video_bitrate, max_bitrate))

            run_ffmpeg_compression(input_path, output_path, video_bitrate, audio_bitrate, 
                                 width, height, format)
            final_size = os.path.getsize(output_path)
            attempt += 1

        # Final check to ensure size is within required range
        if final_size > max_bytes:
            # If still too large, use minimum buffer
            target_size_mb = max_size_mb - BUFFER_MAX
            target_bytes = target_size_mb * 1024 * 1024
            video_bitrate = max(min_bitrate, min(((target_bytes * 8) / duration) - audio_bitrate, max_bitrate))
            run_ffmpeg_compression(input_path, output_path, video_bitrate, audio_bitrate, 
                                 width, height, format)
            final_size = os.path.getsize(output_path)

        final_size_mb = round(final_size / (1024 * 1024), 2)
        return output_path, final_size_mb
        
    except Exception as e:
        logging.error(f"Error in compress_video_to_target: {str(e)}")
        raise
