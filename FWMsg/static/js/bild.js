window.onload = function () {
    return;
    document.getElementById('id_image').addEventListener('change', function (event) {
        const previewContainer = document.getElementById('previewContainer');
        previewContainer.innerHTML = ''; // Clear existing previews

        // Create row div for grid layout
        const row = document.createElement('div');
        row.className = 'row row-cols-2 row-cols-md-4 row-cols-lg-6 g-3';
        previewContainer.appendChild(row);

        // Loop through the selected files
        for (let i = 0; i < event.target.files.length; i++) {
            const file = event.target.files[i];
            const reader = new FileReader();

            // Once the file is read, create preview card
            reader.onload = function (e) {
                const col = document.createElement('div');
                col.className = 'col';

                const card = document.createElement('div');
                card.className = 'card h-100 shadow-sm';
                card.style.border = '1px solid #dee2e6';
                card.style.borderRadius = '0.5rem'; // Add rounded corners to card

                const img = document.createElement('img');
                img.src = e.target.result;
                img.className = 'card-img-top';
                img.style.objectFit = 'cover';
                img.style.height = '150px';
                img.style.border = '1px solid #dee2e6';
                img.style.borderTopLeftRadius = '0.5rem'; // Round top corners of image
                img.style.borderTopRightRadius = '0.5rem';

                const cardBody = document.createElement('div');
                cardBody.className = 'card-body p-2';
                cardBody.style.borderTop = '1px solid #dee2e6';
                cardBody.style.borderBottomLeftRadius = '0.5rem'; // Round bottom corners of card body
                cardBody.style.borderBottomRightRadius = '0.5rem';

                const fileName = document.createElement('p');
                fileName.className = 'card-text small text-muted text-truncate mb-0';
                fileName.textContent = file.name;

                cardBody.appendChild(fileName);
                card.appendChild(img);
                card.appendChild(cardBody);
                col.appendChild(card);
                row.appendChild(col);
            };

            // Read the file as a Data URL (base64 encoded)
            reader.readAsDataURL(file);
        }