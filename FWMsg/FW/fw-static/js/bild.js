window.onload = function () {
    document.getElementById('id_image').addEventListener('change', function (event) {
        const previewContainer = document.getElementById('previewContainer');
        previewContainer.innerHTML = ''; // Clear existing previews

        // Loop through the selected files
        for (let i = 0; i < event.target.files.length; i++) {
            const file = event.target.files[i];
            const reader = new FileReader();

            // Once the file is read, create an image element
            reader.onload = function (e) {
                const img = document.createElement('img');
                img.src = e.target.result;
                img.style.width = '100px'; // Set preview size as needed
                img.style.margin = '5px';
                previewContainer.appendChild(img);
            };

            // Read the file as a Data URL (base64 encoded)
            reader.readAsDataURL(file);
        }
    });
}