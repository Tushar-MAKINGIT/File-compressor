from flask import Flask, request, send_file, jsonify, send_from_directory
from .utils.image_compressor import compress_image, get_file_size
from .utils.pdf_compressor import AdaptivePDFCompressor
from .utils.video_compressor import compress_video_to_target
from flask_cors import CORS
import os
import subprocess
from werkzeug.utils import secure_filename
import io
# import json # Unused
from PIL import Image

# Get the directory where app.py is located
backend_dir = os.path.dirname(os.path.abspath(__file__))
# Construct the path to the frontend directory relative to this script
frontend_dir = os.path.abspath(os.path.join(backend_dir, '..', 'frontend'))  # Frontend is now in the parent directory

# Check if frontend directory exists, provide a warning if not (optional but helpful)
if not os.path.isdir(frontend_dir):
    print(f"Warning: Frontend directory not found at expected location: {frontend_dir}")

# Check if ffmpeg is installed
try:
    subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    FFMPEG_INSTALLED = True
except FileNotFoundError:
    FFMPEG_INSTALLED = False
    print("Warning: FFmpeg is not installed. Video compression will not work.")

app = Flask(__name__, static_folder=frontend_dir, static_url_path='')
CORS(app)  # Allow frontend to call this API

# Configuration
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_PDF_EXTENSIONS = {'pdf'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB max file size for non-video files
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB max file size for videos
MIN_TARGET_SIZE = 5  # Minimum target size in KB

# Get the absolute path for the uploads directory
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
PROCESSED_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'compressed')
print(f"Upload folder path: {UPLOAD_FOLDER}")  # Debug log

# Create upload and processed folders if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
print(f"Upload folder exists after creation: {os.path.exists(UPLOAD_FOLDER)}")  # Debug log

def allowed_file(filename: str, file_type: str) -> bool:
    extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if file_type == 'image':
        return extension in ALLOWED_IMAGE_EXTENSIONS
    elif file_type == 'pdf':
        return extension in ALLOWED_PDF_EXTENSIONS
    elif file_type == 'video':
        return extension in ALLOWED_VIDEO_EXTENSIONS
    return False

@app.route('/')
def serve_frontend():
    # Use the absolute path to frontend_dir
    return send_from_directory(frontend_dir, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    # Use the absolute path to frontend_dir
    return send_from_directory(frontend_dir, path)

@app.route('/compress-image', methods=['POST'])
def compress_file():
    # Validate request has file
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    file_type = request.form.get('file_type', 'image')
    if not allowed_file(file.filename, file_type):
        allowed_extensions = (
            ALLOWED_IMAGE_EXTENSIONS if file_type == 'image' 
            else ALLOWED_PDF_EXTENSIONS if file_type == 'pdf'
            else ALLOWED_VIDEO_EXTENSIONS
        )
        return jsonify({'error': f'Unsupported file type. Please upload {", ".join(allowed_extensions)} files.'}), 400

    # Check ffmpeg installation for video compression
    if file_type == 'video' and not FFMPEG_INSTALLED:
        return jsonify({'error': 'FFmpeg is not installed. Please install FFmpeg to compress videos.'}), 500

    # Validate target size
    try:
        max_size = float(request.form.get('target_size_kb', 500))
        size_format = request.form.get('size_format', 'kb').lower()
        
        # Convert to KB if needed and enforce minimum limits
        if size_format == 'mb':
            if max_size < 1:
                return jsonify({'error': 'Target size must be at least 1MB when using MB format'}), 400
            max_size_kb = int(max_size * 1024)  # Convert MB to KB
        else:
            if max_size < 20:
                return jsonify({'error': 'Target size must be at least 20KB when using KB format'}), 400
            max_size_kb = int(max_size)
            
        if max_size_kb < MIN_TARGET_SIZE:
            return jsonify({'error': f'Target size must be at least {MIN_TARGET_SIZE}KB'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid target size format'}), 400

    # Check file size
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Reset to beginning
    
    if file_type == 'video':
        if size > MAX_VIDEO_SIZE:
            return jsonify({'error': f'Video file too large (max {MAX_VIDEO_SIZE // 1024 // 1024}MB)'}), 400
    else:
        if size > MAX_FILE_SIZE:
            return jsonify({'error': f'File too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)'}), 400

    try:
        if file_type == 'image':
            # Compress the image
            compressed_buffer, new_filename, compression_info = compress_image(file, max_size_kb)
        elif file_type == 'pdf':
            # Initialize PDF compressor
            pdf_compressor = AdaptivePDFCompressor()
            
            # Compress the PDF
            compressed_buffer, compression_info = pdf_compressor.compress_to_target_size(file, max_size_kb)
            
            # Generate filename for compressed PDF
            original_name = secure_filename(file.filename)
            name_without_ext = os.path.splitext(original_name)[0]
            new_filename = f"{name_without_ext}_compressed.pdf"
        else:  # video
            # Save the uploaded video temporarily
            temp_input = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
            file.save(temp_input)
            
            # Convert target size from KB to MB for video compression
            target_size_mb = max_size_kb / 1024
            
            # Compress the video
            output_path, final_size_mb = compress_video_to_target(temp_input, target_size_mb, PROCESSED_FOLDER)
            
            # Read the compressed video
            with open(output_path, 'rb') as f:
                compressed_buffer = io.BytesIO(f.read())
            
            # Generate filename for compressed video
            original_name = secure_filename(file.filename)
            name_without_ext = os.path.splitext(original_name)[0]
            original_ext = os.path.splitext(original_name)[1].lower()
            new_filename = f"{name_without_ext}_compressed{original_ext}"
            
            # Clean up temporary files
            os.remove(temp_input)
            os.remove(output_path)
            
            # Prepare compression info
            compression_info = {
                'original_size': round(size / 1024, 2),
                'compressed_size': round(final_size_mb * 1024, 2),
                'reduction_percent': round((1 - (final_size_mb * 1024) / (size / 1024)) * 100, 2),
                'quality': 'Original' if final_size_mb * 1024 >= size / 1024 else f'{int((final_size_mb * 1024) / (size / 1024) * 100)}%'
            }
        
        # Store the compressed file temporarily
        temp_path = os.path.join(UPLOAD_FOLDER, new_filename)
        print(f"Saving compressed file to: {temp_path}")  # Debug log
        print(f"Upload folder exists: {os.path.exists(UPLOAD_FOLDER)}")  # Debug log
        
        with open(temp_path, 'wb') as f:
            f.write(compressed_buffer.getvalue())
        
        # Verify file was saved
        if not os.path.exists(temp_path):
            return jsonify({'error': 'Failed to save compressed file'}), 500
            
        print(f"File saved successfully: {os.path.exists(temp_path)}")  # Debug log
        
        # Return success response with compression info and file path
        return jsonify({
            'status': 'success',
            'filename': new_filename,
            'compression_info': compression_info,
            'download_url': f'/download/{new_filename}'
        })
        
    except Exception as e:
        print(f"Error during compression: {str(e)}")  # Debug log
        return jsonify({'error': str(e)}), 500

@app.route('/download/<path:filename>')
def download_file(filename):
    try:
        # Decode the URL-encoded filename
        decoded_filename = filename
        print(f"Received filename: {decoded_filename}")  # Debug log
        
        # List all files in the uploads directory
        upload_files = os.listdir(UPLOAD_FOLDER)
        print(f"Available files in uploads: {upload_files}")  # Debug log
        
        # Find the matching file (case-insensitive and space-insensitive)
        matching_file = None
        for file in upload_files:
            if file.replace(' ', '_').lower() == decoded_filename.replace(' ', '_').lower():
                matching_file = file
                break
        
        if not matching_file:
            return jsonify({'error': f'File not found. Available files: {upload_files}'}), 404

        file_path = os.path.join(UPLOAD_FOLDER, matching_file)
        print(f"Downloading file from: {file_path}")  # Debug log
        
        # Return the file directly and delete it after sending
        response = send_file(
            file_path,
            as_attachment=True,
            download_name=matching_file  # Use the original filename for download
        )
        
        # Delete the file after sending
        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Cleaned up file: {file_path}")
            except Exception as e:
                print(f"Error cleaning up file: {str(e)}")
        
        return response
    except Exception as e:
        print(f"Error during download: {str(e)}")  # Debug log
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
