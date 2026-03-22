function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.form-section').forEach(s => s.classList.remove('active'));
    
    if (tabName === 'hide') {
        document.querySelectorAll('.tab')[0].classList.add('active');
        document.getElementById('hide-section').classList.add('active');
    } else {
        document.querySelectorAll('.tab')[1].classList.add('active');
        document.getElementById('extract-section').classList.add('active');
    }
}

function updateFileName(inputElement, msgElementId) {
    const msgElement = document.getElementById(msgElementId);
    if (inputElement.files && inputElement.files.length > 0) {
        msgElement.textContent = "✅ " + inputElement.files[0].name;
        msgElement.style.color = "var(--primary-color)";
    } else {
        msgElement.style.color = "var(--text-muted)";
    }
}

document.getElementById('hide-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const status = document.getElementById('hide-status');
    status.className = 'status loading';
    status.textContent = 'Encrypting and hiding data...';
    
    const formData = new FormData();
    formData.append('cover', document.getElementById('cover-img').files[0]);
    formData.append('secret', document.getElementById('secret-img').files[0]);

    fetch('/hide', { method: 'POST', body: formData })
    .then(response => {
        if (!response.ok) throw new Error("Processing failed.");
        return response.blob();
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'StegoVault_Data.zip';
        a.click();
        status.className = 'status success';
        status.innerHTML = '✅ Success! <b>StegoVault_Data.zip</b> downloaded.';
    })
    .catch(err => {
        status.className = 'status error';
        status.textContent = '❌ Error: Could not process images.';
    });
});

document.getElementById('extract-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const status = document.getElementById('extract-status');
    status.className = 'status loading';
    status.textContent = 'Extracting and decrypting data...';
    
    const formData = new FormData();
    formData.append('stego', document.getElementById('stego-img').files[0]);
    formData.append('key', document.getElementById('aes-key').files[0]);
    formData.append('meta', document.getElementById('meta-file').files[0]);

    fetch('/extract', { method: 'POST', body: formData })
    .then(response => {
        if (!response.ok) throw new Error("Processing failed.");
        return response.blob();
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'recovered_secret.png';
        a.click();
        status.className = 'status success';
        status.innerHTML = '✅ Success! <b>recovered_secret.png</b> downloaded.';
    })
    .catch(err => {
        status.className = 'status error';
        status.textContent = '❌ Error: Extraction failed. Check your files.';
    });
});