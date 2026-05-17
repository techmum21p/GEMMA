// Camera capture using getUserMedia (Android Chrome)

function openCamera() {
  const cameraInput = document.getElementById('camera-input');
  cameraInput.click();
}

function handleCameraCapture(event) {
  const file = event.target.files[0];
  if (!file) return;
  _processImageFile(file);
  event.target.value = '';
}

function openGallery() {
  const galleryInput = document.getElementById('gallery-input');
  galleryInput.click();
}

function handleGalleryUpload(event) {
  const file = event.target.files[0];
  if (!file) return;
  _processImageFile(file);
  event.target.value = '';
}

function handleFileSelect(event) {
  const file = event.target.files[0];
  if (!file) return;
  _processImageFile(file);
  event.target.value = '';
}

function _processImageFile(file) {
  const mimeType = file.type || '';
  const fileName = (file.name || '').toLowerCase();
  const isImage = mimeType.startsWith('image/') || /\.(jpe?g|png|gif|webp|heic|heif|avif|bmp)$/.test(fileName);
  if (!isImage) {
    if (typeof showError === 'function') showError('Mangyaring pumili ng larawan (JPG, PNG, etc.).');
    return;
  }

  const maxSize = 5 * 1024 * 1024;
  if (file.size > maxSize) {
    if (typeof showError === 'function') showError('Masyadong malaki ang larawan. Maximum 5MB lamang.');
    return;
  }

  state.capturedImageFile = file;

  const reader = new FileReader();
  reader.onload = (e) => {
    const preview = document.getElementById('camera-preview');
    const container = document.getElementById('camera-preview-container');
    if (preview && container) {
      preview.src = e.target.result;
      container.classList.remove('hidden');
    }
  };
  reader.readAsDataURL(file);

  if (typeof showToast === 'function') showToast('Larawan naka-attach na!');
}

function clearPhoto() {
  state.capturedImageFile = null;
  state.capturedImagePath = null;

  const preview = document.getElementById('camera-preview');
  const container = document.getElementById('camera-preview-container');
  if (preview) preview.src = '';
  if (container) container.classList.add('hidden');
}
