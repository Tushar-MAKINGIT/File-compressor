const form = document.getElementById('upload-form');
const fileInput = document.getElementById('file-input');
const fileTypeSelect = document.getElementById('file-type');
const dropZone = document.getElementById('drop-zone');
const dropText = document.getElementById('drop-text');
const loader = document.getElementById('loader');
const compressBtn = document.getElementById('compress-btn');
const fileInfo = document.getElementById('file-info');
const targetSizeInput = document.getElementById('target-size');
const resultDiv = document.getElementById('compression-result');
const downloadBtn = document.getElementById('download-btn');

let currentDownloadUrl = null;
let fileTypeMap = {
    'image': ['.png', '.jpeg', '.jpg', '.webp', '.gif'],
    'video': ['.mp4', '.mov', '.avi', '.mkv', '.webm'],
    'pdf': ['.pdf']
};

// Update file input based on file type selection
fileTypeSelect.addEventListener('change', () => {
    const selectedType = fileTypeSelect.value;
    const sizeFormat = document.getElementById('size-format');
    const sizeInput = document.getElementById('target-size');
    const helpText = document.getElementById('size-help-text');
    
    if (selectedType) {
        // Update file input accept attribute
        fileInput.accept = fileTypeMap[selectedType].join(',');
        fileInput.disabled = false;
        
        // Update drop zone text
        dropText.textContent = `Drag & Drop your ${selectedType} here or click to browse`;
        dropZone.classList.remove('disabled');
        
        // Enable compress button
        compressBtn.disabled = false;

        // Handle size input based on file type
        if (selectedType === 'video') {
            // Force MB format for videos
            sizeFormat.value = 'mb';
            sizeFormat.disabled = true;
            sizeInput.min = 5;
            sizeInput.value = '';  // Clear the value
            sizeInput.placeholder = 'e.g., 20';
            helpText.textContent = 'Minimum: 5MB. File will be compressed to slightly below this size.';
        } else {
            // Enable format selection for other file types
            sizeFormat.disabled = false;
            sizeInput.value = '';  // Clear the value
            if (sizeFormat.value === 'mb') {
                sizeInput.min = 1;
                sizeInput.placeholder = 'e.g., 1';
                helpText.textContent = 'Minimum: 1MB. File will be compressed to slightly below this size. If you want to compress even more, switch to KB.';
            } else {
                sizeInput.min = 20;
                sizeInput.placeholder = 'e.g., 500';
                helpText.textContent = 'Minimum: 20KB. File will be compressed to slightly below this size.';
            }
        }
    } else {
        fileInput.disabled = true;
        dropZone.classList.add('disabled');
        dropText.textContent = 'Select a file type above first';
        compressBtn.disabled = true;
        sizeFormat.disabled = false;
    }
    
    // Clear any previously selected file
    fileInput.value = '';
    fileInfo.style.display = 'none';
    hideResults();
});

// File selected via browsing
fileInput.addEventListener('change', () => {
    validateFileType();
    validateFileSize();
    showFileName();
    hideResults();
});

// Drag over drop zone
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    if (!fileInput.disabled) {
        dropZone.style.backgroundColor = '#fef0e8';
    }
});

dropZone.addEventListener('dragleave', () => {
    dropZone.style.backgroundColor = '';
});

// File dropped
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.style.backgroundColor = '';
    
    if (fileInput.disabled) return;
    
    if (e.dataTransfer.files.length) {
        const file = e.dataTransfer.files[0];
        const fileType = fileTypeSelect.value;
        const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
        
        // Check if file type matches selected type
        if (!fileTypeMap[fileType].includes(fileExtension)) {
            showCustomPopup(`Please select a valid ${fileType} file. Supported formats: ${fileTypeMap[fileType].join(', ')}`);
            return;
        }
        
        // Set the file to the file input
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        fileInput.files = dataTransfer.files;
        
        if (validateFileSize()) {
            showFileName();
            hideResults();
        }
    }
});

// Validate file type matches selected type
function validateFileType() {
    const file = fileInput.files[0];
    if (!file) return;
    
    const selectedType = fileTypeSelect.value;
    const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
    
    if (!fileTypeMap[selectedType].includes(fileExtension)) {
        alert(`Please select a valid ${selectedType} file. Supported formats: ${fileTypeMap[selectedType].join(', ')}`);
        fileInput.value = '';
        fileInfo.style.display = 'none';
    }
}

// Show compression results
function showResults(info) {
    const sizeFormat = document.getElementById('size-format').value;
    let originalSize, compressedSize;
    
    if (sizeFormat === 'mb') {
        originalSize = (info.original_size / 1024).toFixed(2);
        compressedSize = (info.compressed_size / 1024).toFixed(2);
    } else {
        originalSize = info.original_size;
        compressedSize = info.compressed_size;
    }

    resultDiv.innerHTML = `
        <div class="result-card">
            <h3>Compression Results</h3>
            <p>Original Size: ${originalSize} ${sizeFormat.toUpperCase()}</p>
            <p>Compressed Size: ${compressedSize} ${sizeFormat.toUpperCase()}</p>
            <p>Reduction: ${info.reduction_percent}%</p>
            <p>Quality Used: ${info.quality}</p>
        </div>
    `;
    resultDiv.style.display = 'block';
    downloadBtn.style.display = 'block';
}

function hideResults() {
    resultDiv.style.display = 'none';
    downloadBtn.style.display = 'none';
    currentDownloadUrl = null;
}

// Handle download button click
downloadBtn.addEventListener('click', async () => {
    if (currentDownloadUrl) {
        try {
            const response = await fetch(currentDownloadUrl);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Download failed');
            }
            
            // Get the filename from the response headers
            const contentDisposition = response.headers.get('Content-Disposition');
            const filename = contentDisposition
                ? contentDisposition.split('filename=')[1].replace(/"/g, '')
                : `compressed_${fileTypeSelect.value}.${fileInput.files[0].name.split('.').pop()}`;
            
            // Create a blob from the response
            const blob = await response.blob();
            
            // Create a download link and trigger it
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (error) {
            resultDiv.innerHTML = `<p class="error-message">Error: ${error.message}</p>`;
            resultDiv.style.display = 'block';
        }
    }
});

// Add this function to create and show the custom popup
function showCustomPopup(message) {
    // Remove any existing popup
    const existingPopup = document.querySelector('.custom-popup');
    const existingOverlay = document.querySelector('.popup-overlay');
    if (existingPopup) {
        existingPopup.remove();
    }
    if (existingOverlay) {
        existingOverlay.remove();
    }

    // Create overlay
    const overlay = document.createElement('div');
    overlay.className = 'popup-overlay';
    document.body.appendChild(overlay);

    // Create popup element
    const popup = document.createElement('div');
    popup.className = 'custom-popup';
    popup.innerHTML = `
        <span class="warning-icon">!</span>
        <span class="popup-message">${message}</span>
    `;

    // Add popup to body
    document.body.appendChild(popup);

    // Remove popup and overlay after 3 seconds
    setTimeout(() => {
        popup.remove();
        overlay.remove();
    }, 3000);
}

// Submit form
form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const file = fileInput.files[0];
    const targetSize = parseFloat(targetSizeInput.value);
    const fileType = fileTypeSelect.value;
    const sizeFormat = document.getElementById('size-format').value;

    // Validate file type first
    if (!fileType) {
        alert("Please select a file type.");
        return;
    }

    if (!file) {
        alert(`Please select a ${fileType} file.`);
        return;
    }

    // Validate input file size
    const fileSizeKB = file.size / 1024;
    if ((fileType === 'image' || fileType === 'pdf') && fileSizeKB < 20) {
        showCustomPopup("File size must be greater than 20KB to compress.");
        return;
    }

    // Validate target size requirements
    if (!targetSize) {
        showCustomPopup("Please enter a maximum target size.");
        return;
    }

    // Size validation based on format
    if (sizeFormat === 'mb') {
        if (!Number.isInteger(targetSize)) {
            showCustomPopup("Value must be greater than or equal to 1MB. If you want to compress even less, switch to KB.");
            return;
        }
        if (targetSize < 1) {
            showCustomPopup("Value must be greater than or equal to 1MB. If you want to compress even less, switch to KB.");
            return;
        }
    } else { // KB format
        if (targetSize < 20) {
            showCustomPopup("Value must be greater than or equal to 20KB.");
            return;
        }
    }

    // Convert MB to KB if necessary
    const targetSizeKB = sizeFormat === 'mb' ? targetSize * 1024 : targetSize;

    // Only proceed with compression if all validations pass
    loader.style.display = 'inline-block';
    compressBtn.disabled = true;
    compressBtn.textContent = 'Compressing...';
    hideResults();

    const formData = new FormData();
    formData.append("file", file);
    formData.append("target_size_kb", targetSizeKB);
    formData.append("file_type", fileType);
    formData.append("size_format", sizeFormat);

    try {
        // Use the correct backend endpoint with timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 minute timeout

        const response = await fetch('/compress-image', {
            method: "POST",
            body: formData,
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        // First check if the response is ok
        if (!response.ok) {
            const errorText = await response.text();
            let errorMessage;
            try {
                const errorData = JSON.parse(errorText);
                errorMessage = errorData.error || 'Compression failed';
            } catch (parseError) {
                console.error('Error parsing error response:', errorText);
                errorMessage = 'Compression failed - server error';
            }
            throw new Error(errorMessage);
        }

        // Try to parse the successful response
        let data;
        try {
            const responseText = await response.text();
            console.log('Raw response:', responseText); // Debug log
            data = JSON.parse(responseText);
        } catch (parseError) {
            console.error('Error parsing success response:', parseError);
            throw new Error('Failed to parse server response');
        }

        if (!data || !data.compression_info) {
            throw new Error('Invalid response format from server');
        }

        // Show compression results
        showResults(data.compression_info);
        // Encode the filename for the URL
        currentDownloadUrl = `/download/${encodeURIComponent(data.filename)}`;
        
    } catch (error) {
        console.error('Compression error:', error);
        // Display error message in the result area
        let errorMessage = error.name === 'AbortError' 
            ? 'Compression timed out. Please try again with a smaller file or higher target size.'
            : `Error: ${error.message}`;
        
        resultDiv.innerHTML = `<p class="error-message">${errorMessage}</p>`;
        resultDiv.style.display = 'block';
        downloadBtn.style.display = 'none';
        currentDownloadUrl = null;
    } finally {
        loader.style.display = 'none';
        compressBtn.disabled = false;
        compressBtn.textContent = 'Compress File';
    }
});

// Display file name
function showFileName() {
    const file = fileInput.files[0];
    if (file) {
        fileInfo.style.display = 'block';
        fileInfo.textContent = `✅ ${file.name} has been added`;
    } else {
        fileInfo.style.display = 'none';
        fileInfo.textContent = '';
    }
}

// Initialize UI
dropZone.classList.add('disabled');

// Update the validateSize function
function validateSize() {
    const sizeInput = document.getElementById('target-size');
    const sizeFormat = document.getElementById('size-format').value;
    const fileType = document.getElementById('file-type').value;
    const value = parseFloat(sizeInput.value);
    const helpText = document.getElementById('size-help-text');
    
    if (!value) {
        helpText.textContent = ''; // Clear any existing message
        return;
    }

    if (sizeFormat === 'mb') {
        helpText.textContent = `Minimum value : 1MB. File will be compressed to slightly below this size. If you want to compress even more, switch to KB.`;
        helpText.style.color = '#666';
    } else { // KB format
        helpText.textContent = `Minimum value: 20KB. File will be compressed to slightly below this size.`;
        helpText.style.color = '#666';
    }
}

// Update the size format change handler
document.getElementById('size-format').addEventListener('change', function() {
    const sizeInput = document.getElementById('target-size');
    const fileType = document.getElementById('file-type').value;
    
    // Clear the input value when switching formats
    sizeInput.value = '';
    
    if (this.value === 'mb') {
        sizeInput.min = fileType === 'video' ? 5 : 1;
        sizeInput.placeholder = fileType === 'video' ? 'e.g., 20' : 'e.g., 1';
        document.getElementById('size-help-text').textContent = fileType === 'video' ? 
            'Minimum: 5MB. Maximum: 100MB. File will be compressed to slightly below target size.' :
            'Minimum: 1MB. File will be compressed to slightly below this size. If you want to compress even more, switch to KB.';
    } else {
        sizeInput.min = 20;
        sizeInput.placeholder = 'e.g., 500';
        document.getElementById('size-help-text').textContent = 'Minimum: 20KB. File will be compressed to slightly below this size.';
    }
});

// Update the compression result display
function displayCompressionResult(result) {
    const resultDiv = document.getElementById('compression-result');
    const sizeFormat = document.getElementById('size-format').value;
    
    let originalSize, compressedSize;
    if (sizeFormat === 'mb') {
        originalSize = (result.original_size / 1024).toFixed(2);
        compressedSize = (result.compressed_size / 1024).toFixed(2);
    } else {
        originalSize = result.original_size;
        compressedSize = result.compressed_size;
    }
    
    resultDiv.innerHTML = `
        <h3>Compression Results</h3>
        <p>Original Size: ${originalSize} ${sizeFormat.toUpperCase()}</p>
        <p>Compressed Size: ${compressedSize} ${sizeFormat.toUpperCase()}</p>
        <p>Reduction: ${result.reduction_percent}%</p>
    `;
    resultDiv.style.display = 'block';
}

// Add file size validation function
function validateFileSize() {
    const file = fileInput.files[0];
    const fileType = fileTypeSelect.value;
    
    if (!file) return;

    // Convert file size to MB for videos, KB for others
    const fileSizeKB = file.size / 1024;
    const fileSizeMB = fileSizeKB / 1024;

    if (fileType === 'video') {
        if (fileSizeMB < 5) {
            showCustomPopup("Video file size must be at least 5MB to compress.");
            fileInput.value = '';
            fileInfo.style.display = 'none';
            return false;
        }
        if (fileSizeMB > 100) {  // 100MB
            showCustomPopup("Video file size must be less than 100MB.");
            fileInput.value = '';
            fileInfo.style.display = 'none';
            return false;
        }
    } else if ((fileType === 'image' || fileType === 'pdf') && fileSizeKB < 20) {
        showCustomPopup("File size must be greater than 20KB to compress.");
        fileInput.value = '';
        fileInfo.style.display = 'none';
        return false;
    }
    return true;
}
