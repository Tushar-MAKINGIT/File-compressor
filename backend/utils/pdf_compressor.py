#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
from pathlib import Path
import shutil
import tempfile
import io

class AdaptivePDFCompressor:
    """
    Adaptively compresses PDF files to meet a target file size using Ghostscript.
    Uses binary search to efficiently find optimal compression settings that still
    maintain acceptable quality.
    """

    # Define preset quality levels with their parameters
    PRESETS = {
        "screen": {
            "gs_preset": "/screen",   # Built-in Ghostscript preset (lowest quality)
            "dpi": 72,
            "description": "Low quality, smallest file size"
        },
        "ebook": {
            "gs_preset": "/ebook",    # Built-in Ghostscript preset (medium quality)
            "dpi": 150,
            "description": "Medium quality, small file size"
        },
        "printer": {
            "gs_preset": "/printer",  # Built-in Ghostscript preset (better quality)
            "dpi": 300,
            "description": "High quality, medium file size"
        },
        "prepress": {
            "gs_preset": "/prepress", # Built-in Ghostscript preset (highest quality)
            "dpi": 300,
            "description": "High quality, larger file size"
        },
        "default": {
            "gs_preset": "/default",  # Default Ghostscript preset
            "dpi": 300,
            "description": "Default quality level"
        }
    }

    # Additional quality levels between the presets
    CUSTOM_QUALITY_LEVELS = [
        # Custom ultra-low quality settings 
        {"quality_factor": 0.0, "gs_preset": "/screen", "dpi": 36},
        {"quality_factor": 0.1, "gs_preset": "/screen", "dpi": 50},
        {"quality_factor": 0.2, "gs_preset": "/screen", "dpi": 72},
        {"quality_factor": 0.3, "gs_preset": "/ebook", "dpi": 100},
        {"quality_factor": 0.4, "gs_preset": "/ebook", "dpi": 150},
        {"quality_factor": 0.5, "gs_preset": "/ebook", "dpi": 200},
        {"quality_factor": 0.6, "gs_preset": "/printer", "dpi": 225},
        {"quality_factor": 0.7, "gs_preset": "/printer", "dpi": 250},
        {"quality_factor": 0.8, "gs_preset": "/printer", "dpi": 300},
        {"quality_factor": 0.9, "gs_preset": "/prepress", "dpi": 300},
        {"quality_factor": 1.0, "gs_preset": "/prepress", "dpi": 400}
    ]

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.temp_dir = None
        self.gs_path = self._get_ghostscript_path()

    def log(self, message):
        if self.verbose:
            print(f"[INFO] {message}")

    def _get_ghostscript_path(self):
        """Get the appropriate Ghostscript path for the current system"""
        try:
            # First try the hardcoded path for Windows
            gs_path = r"C:\Program Files\gs\gs10.05.0\bin\gswin64c.exe"
            if not os.path.exists(gs_path):
                # Try using the command directly (relying on PATH)
                gs_path = "gs" if os.name != "nt" else "gswin64c"
            
            result = subprocess.run([gs_path, '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                self.log(f"Ghostscript version: {result.stdout.strip()}")
                return gs_path
            raise RuntimeError("Ghostscript check failed")
        except FileNotFoundError:
            raise RuntimeError("Ghostscript not found. Please install Ghostscript.")

    def get_file_size_mb(self, file_path):
        """Get file size in megabytes"""
        return os.path.getsize(file_path) / (1024 * 1024)

    def get_file_size_kb(self, file_path):
        """Get file size in kilobytes"""
        return os.path.getsize(file_path) / 1024

    def compress_pdf(self, input_path, output_path, quality_settings):
        """Compress PDF using Ghostscript with specified quality settings"""
        # Build the Ghostscript command with reliable parameters
        gs_cmd = [
            self.gs_path,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.5",
            f"-dPDFSETTINGS={quality_settings['gs_preset']}",
            f"-dDownsampleColorImages=true",
            f"-dDownsampleGrayImages=true", 
            f"-dDownsampleMonoImages=true",
            f"-dColorImageResolution={quality_settings['dpi']}",
            f"-dGrayImageResolution={quality_settings['dpi']}",
            f"-dMonoImageResolution={quality_settings['dpi']}",
            "-dNOPAUSE",
            "-dBATCH",
            "-dQUIET",
            f"-sOutputFile={output_path}",
            input_path
        ]

        self.log(f"Running Ghostscript with preset={quality_settings['gs_preset']}, dpi={quality_settings['dpi']}")
        
        # Run the command and capture output
        result = subprocess.run(gs_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            error_msg = result.stderr.strip() or "Unknown error"
            self.log(f"Ghostscript error: {error_msg}")
            raise RuntimeError(f"Ghostscript failed: {error_msg}")

    def get_settings_for_quality_factor(self, quality_factor):
        """Get settings for a given quality factor (0.0-1.0)"""
        # Find the closest predefined quality level
        for i, level in enumerate(self.CUSTOM_QUALITY_LEVELS):
            if quality_factor <= level["quality_factor"]:
                return level
        # Default to highest quality if no match
        return self.CUSTOM_QUALITY_LEVELS[-1]

    def find_optimal_compression(self, input_path, target_size_mb, output_path=None):
        """Find optimal compression settings to meet target size in MB"""
        input_size_mb = self.get_file_size_mb(input_path)

        if input_size_mb <= target_size_mb:
            self.log(f"Input file already smaller than target size ({input_size_mb:.2f}MB ≤ {target_size_mb:.2f}MB)")
            if output_path:
                shutil.copy2(input_path, output_path)
                return output_path, input_size_mb
            return input_path, input_size_mb

        # Create temporary directory for intermediate files
        self.temp_dir = tempfile.mkdtemp()
        self.log(f"Created temporary directory: {self.temp_dir}")

        try:
            # Try lowest quality first to check if target is achievable
            lowest_settings = self.get_settings_for_quality_factor(0.0)
            lowest_output_path = os.path.join(self.temp_dir, "lowest_quality.pdf")
            self.compress_pdf(input_path, lowest_output_path, lowest_settings)
            lowest_size_mb = self.get_file_size_mb(lowest_output_path)
            
            self.log(f"Lowest quality compression result: {lowest_size_mb:.2f}MB (target: {target_size_mb:.2f}MB)")
            
            if lowest_size_mb > target_size_mb:
                self.log("Warning: Cannot achieve target size even with maximum compression")
                if output_path:
                    shutil.copy2(lowest_output_path, output_path)
                    final_path = output_path
                else:
                    input_filename = os.path.basename(input_path)
                    name, ext = os.path.splitext(input_filename)
                    final_path = f"{name}_compressed{ext}"
                    shutil.copy2(lowest_output_path, final_path)
                
                return final_path, lowest_size_mb
            
            # Try highest quality to see if it already meets target
            highest_settings = self.get_settings_for_quality_factor(1.0)
            highest_output_path = os.path.join(self.temp_dir, "highest_quality.pdf")
            self.compress_pdf(input_path, highest_output_path, highest_settings)
            highest_size_mb = self.get_file_size_mb(highest_output_path)
            
            self.log(f"Highest quality compression result: {highest_size_mb:.2f}MB (target: {target_size_mb:.2f}MB)")
            
            if highest_size_mb <= target_size_mb:
                self.log("Highest quality meets target size requirement")
                if output_path:
                    shutil.copy2(highest_output_path, output_path)
                    final_path = output_path
                else:
                    input_filename = os.path.basename(input_path)
                    name, ext = os.path.splitext(input_filename)
                    final_path = f"{name}_compressed{ext}"
                    shutil.copy2(highest_output_path, final_path)
                
                return final_path, highest_size_mb
            
            # Binary search to find optimal quality setting
            low, high = 0.0, 1.0
            best_output_path = lowest_output_path
            best_size_mb = lowest_size_mb
            best_quality = 0.0
            
            iteration = 0
            max_iterations = 8  # Limit number of iterations
            
            while (high - low) > 0.05 and iteration < max_iterations:
                iteration += 1
                mid = (low + high) / 2
                settings = self.get_settings_for_quality_factor(mid)
                output_path_temp = os.path.join(self.temp_dir, f"quality_{mid:.2f}.pdf")
                
                try:
                    self.compress_pdf(input_path, output_path_temp, settings)
                    current_size_mb = self.get_file_size_mb(output_path_temp)
                    
                    self.log(f"Iteration {iteration}: quality={mid:.2f}, size={current_size_mb:.2f}MB")
                    
                    if current_size_mb <= target_size_mb:
                        # This quality meets the target size constraint
                        if current_size_mb > best_size_mb:
                            # Keep the largest file that still meets the constraint
                            best_output_path = output_path_temp
                            best_size_mb = current_size_mb
                            best_quality = mid
                        low = mid  # Search for even higher quality that still meets target
                    else:
                        # This quality exceeds target size, search for lower quality
                        high = mid
                except Exception as e:
                    self.log(f"Error during iteration {iteration}: {e}")
                    # If an error occurs, try a different quality level
                    high = mid
            
            self.log(f"Best quality factor found: {best_quality:.2f} with size {best_size_mb:.2f}MB")
            
            # Copy the best result to the final location
            if output_path:
                shutil.copy2(best_output_path, output_path)
                final_path = output_path
            else:
                input_filename = os.path.basename(input_path)
                name, ext = os.path.splitext(input_filename)
                final_path = f"{name}_compressed{ext}"
                shutil.copy2(best_output_path, final_path)

            return final_path, best_size_mb

        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up temporary files and directory"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            self.log(f"Cleaned up temporary directory: {self.temp_dir}")
            self.temp_dir = None

    def compress_to_target_size(self, input_file, target_size_kb):
        """
        Compress a PDF file to a target size in KB.
        
        Args:
            input_file: File object or path to the input PDF
            target_size_kb: Target size in KB
            
        Returns:
            tuple: (compressed_buffer, compression_info)
        """
        try:
            # Create a temporary file for the input
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_input:
                if isinstance(input_file, io.IOBase):
                    # If input is a file object, save its contents to the temp file
                    input_file.seek(0)  # Ensure we're at the start of the file
                    temp_input.write(input_file.read())
                    input_file.seek(0)  # Reset file pointer for potential future use
                else:
                    # If input is a path, copy the file
                    with open(input_file, 'rb') as f:
                        temp_input.write(f.read())
                temp_input_path = temp_input.name

            # Get the original file size in KB before any processing
            original_size_kb = self.get_file_size_kb(temp_input_path)
            self.log(f"Original file size: {original_size_kb:.2f} KB")
            
            # Convert target size from KB to MB for the compression function
            target_size_mb = target_size_kb / 1024  # Convert KB to MB
            self.log(f"Target size: {target_size_mb:.2f} MB")
            
            # Find optimal compression
            compressed_path, final_size_mb = self.find_optimal_compression(
                temp_input_path,
                target_size_mb
            )
            
            # Get the actual size of the compressed file
            final_size_kb = self.get_file_size_kb(compressed_path)
            self.log(f"Final compressed size: {final_size_kb:.2f} KB")
            
            # Read the compressed file into a buffer
            with open(compressed_path, 'rb') as f:
                compressed_buffer = io.BytesIO(f.read())
            
            # Calculate compression info with more precise calculations
            reduction_percent = ((original_size_kb - final_size_kb) / original_size_kb) * 100
            quality_percent = (final_size_kb / original_size_kb) * 100
            
            compression_info = {
                'original_size': round(original_size_kb, 2),
                'compressed_size': round(final_size_kb, 2),
                'reduction_percent': round(reduction_percent, 2),
                'quality': 'Original' if final_size_kb >= original_size_kb else f'{int(quality_percent)}%'
            }
            
            self.log(f"Compression results: {compression_info}")
            
            # Clean up temporary files
            try:
                os.unlink(temp_input_path)
                os.unlink(compressed_path)
            except Exception as e:
                self.log(f"Warning: Error cleaning up temporary files: {e}")
            
            return compressed_buffer, compression_info
            
        except Exception as e:
            self.log(f"Error during compression: {e}")
            # Clean up any temporary files that might have been created
            try:
                if 'temp_input_path' in locals() and os.path.exists(temp_input_path):
                    os.unlink(temp_input_path)
                if 'compressed_path' in locals() and os.path.exists(compressed_path):
                    os.unlink(compressed_path)
            except Exception as cleanup_error:
                self.log(f"Error during cleanup: {cleanup_error}")
            raise

def main():
    parser = argparse.ArgumentParser(description="Adaptive PDF Compressor")
    parser.add_argument("input_file", help="Input PDF file path")
    parser.add_argument("--output", "-o", help="Output PDF file path (optional)")
    parser.add_argument("--target-size", "-t", type=float, required=True,
                      help="Target file size in MB")
    parser.add_argument("--verbose", "-v", action="store_true",
                      help="Enable verbose logging")

    args = parser.parse_args()

    compressor = AdaptivePDFCompressor(verbose=args.verbose)
    if not compressor.check_ghostscript():
        print("Error: Ghostscript not found. Please install Ghostscript first.")
        sys.exit(1)

    try:
        output_path, final_size = compressor.find_optimal_compression(
            args.input_file, args.target_size, args.output)
        print(f"\nCompression complete!")
        print(f"Output file: {output_path}")
        print(f"Final size: {final_size:.2f}MB")
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 
