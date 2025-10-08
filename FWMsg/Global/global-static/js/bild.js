window.onload = function () {
    initFullscreenDropZone('id_image', {
        multiple: true,
        onFileSelect: function (file) {
            handleFileSelect(file);
        }
    });

    function handleFileSelect(files) {
        const previewContainer = document.getElementById('previewContainer');
        previewContainer.innerHTML = ''; // Clear existing previews

        // Create row div for grid layout
        const row = document.createElement('div');
        row.className = 'row row-cols-2 row-cols-md-4 row-cols-lg-6 g-3';
        previewContainer.appendChild(row);

        // Loop through selected files
        const fileList = Array.from(files);
        fileList.forEach((file, index) => {
            const reader = new FileReader();

            reader.onload = function (e) {
                const col = document.createElement('div');
                col.className = 'col';

                const card = document.createElement('div');
                card.className = 'card h-100 shadow-sm';
                card.style.border = '1px solid #dee2e6';
                card.style.borderRadius = '0.5rem';

                const img = document.createElement('img');
                img.src = e.target.result;
                img.className = 'card-img-top';
                img.style.objectFit = 'cover';
                img.style.height = '150px';
                img.style.borderTopLeftRadius = '0.5rem';
                img.style.borderTopRightRadius = '0.5rem';

                const cardBody = document.createElement('div');
                cardBody.className = 'card-body p-2';
                cardBody.style.borderTop = '1px solid #dee2e6';


                const fileName = document.createElement('p');
                fileName.className = 'card-text small text-muted text-truncate mb-0';
                fileName.textContent = file.name;

                const removeBtn = document.createElement('input');
                removeBtn.className = 'btn btn-close position-absolute top-0 end-0 m-2';
                removeBtn.style.backgroundColor = '#dc3545';
                removeBtn.style.opacity = '0.8';
                removeBtn.type = 'button';
                removeBtn.onclick = function () {
                    // Remove the file from FileList
                    const dt = new DataTransfer();
                    const input = document.getElementById('id_image');
                    const { files } = input;

                    for (let i = 0; i < files.length; i++) {
                        if (i !== index) {
                            dt.items.add(files[i]);
                        }
                    }

                    input.files = dt.files;
                    col.remove();
                };

                cardBody.appendChild(fileName);
                cardBody.appendChild(removeBtn);
                card.appendChild(img);
                card.appendChild(cardBody);
                col.appendChild(card);
                row.appendChild(col);
            };

            reader.readAsDataURL(file);
        });
    }
}