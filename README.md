# File Compressor
A web-based tool for compressing images, videos, and PDF files while maintaining optimal quality.

## Description
File Compressor is a powerful web application that helps users reduce file sizes without compromising quality. It's particularly useful for web developers, content creators, and anyone who needs to optimize files for sharing or storage. The application uses advanced compression algorithms to ensure the best possible quality at the target file size.

## Features
- **Multiple File Type Support**
  - Images: PNG, JPG, JPEG, GIF, WEBP
  - Videos: MP4, MOV, AVI, MKV, WEBM
  - PDF files
- **Quality Control**
  - Set custom target sizes in KB or MB
  - Maintains optimal quality
  - Adaptive compression algorithms
- **User-Friendly Interface**
  - Drag and drop file upload
  - Real-time compression results
  - Progress indicators
  - Responsive design

## Installation
1. Clone the repository:
```bash
git clone https://github.com/yourusername/file-compressor.git
cd file-compressor
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install FFmpeg:
   - Windows: Download from [FFmpeg website](https://ffmpeg.org/download.html)
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt-get install ffmpeg`

## Usage
1. Start the backend server:
```bash
cd backend
python app.py
```

2. Open your browser and navigate to:
```
http://localhost:5000
```

3. Use the application:
   - Select file type (Image, Video, or PDF)
   - Upload your file
   - Set target size
   - Click compress
   - Download the compressed file

## File Size Limits
- Images and PDFs: 20KB - 50MB
- Videos: 5MB - 100MB
