from flask import Flask, render_template, request, send_file, jsonify
import numpy as np
from PIL import Image
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import json
import io
import zipfile

app = Flask(__name__)

def pad(data):
    pad_len = 16 - (len(data) % 16)
    return data + bytes([pad_len]) * pad_len

def unpad(data):
    pad_len = data[-1]
    return data[:-pad_len]

def encrypt_data(data, key):
    cipher = AES.new(key, AES.MODE_ECB)
    return cipher.encrypt(pad(data))

def decrypt_data(data, key):
    cipher = AES.new(key, AES.MODE_ECB)
    return unpad(cipher.decrypt(data))

def next_pow2(n):
    return int(2**np.ceil(np.log2(int(n))))

def fwht_1d(x):
    a = x.astype(np.float64).copy()
    n = a.shape[0]
    h = 1
    while h < n:
        for i in range(0, n, 2*h):
            u = a[i:i+h].copy()
            v = a[i+h:i+2*h].copy()
            a[i:i+h] = u + v
            a[i+h:i+2*h] = u - v
        h *= 2
    return a

def ifwht_1d(x):
    return fwht_1d(x)/x.shape[0]

def fwht_2d(img):
    tmp = np.apply_along_axis(fwht_1d, 1, img)
    return np.apply_along_axis(fwht_1d, 0, tmp)

def ifwht_2d(coeff):
    tmp = np.apply_along_axis(ifwht_1d, 1, np.apply_along_axis(ifwht_1d, 0, coeff))
    return tmp

def hide_data_in_image(cover_img, secret_data):
    data_bits = ''.join(format(byte, '08b') for byte in secret_data)
    img = np.array(cover_img)
    flat_int = img.flatten().astype(np.int32)
    if len(data_bits) > len(flat_int):
        raise ValueError("Secret image too large for cover image!")
    for i in range(len(data_bits)):
        flat_int[i] = (flat_int[i] & ~1) | int(data_bits[i])
    stego_array = np.clip(flat_int, 0, 255).astype(np.uint8)
    return stego_array.reshape(img.shape)

def extract_data_from_image(stego_img, data_length):
    img = np.array(stego_img)
    flat = img.flatten()
    bits = [str(flat[i] & 1) for i in range(data_length * 8)]
    bytes_data = [int(''.join(bits[i:i+8]), 2) for i in range(0, len(bits), 8)]
    return bytes(bytes_data)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/hide', methods=['POST'])
def hide():
    try:
        cover_file = request.files['cover']
        secret_file = request.files['secret']
        
        cover = Image.open(cover_file).convert("RGB")
        secret = Image.open(secret_file).convert("L")
        
        cover_capacity_bytes = np.array(cover).size // 8
        secret_pixels = secret.size[0] * secret.size[1]
        if secret_pixels > cover_capacity_bytes:
            scale = (cover_capacity_bytes / secret_pixels) ** 0.5
            new_size = (max(1, int(secret.size[0]*scale)), max(1, int(secret.size[1]*scale)))
            secret = secret.resize(new_size)
            
        secret_array = np.array(secret)
        h, w = secret_array.shape
        H, W = next_pow2(h), next_pow2(w)
        
        padded = np.zeros((H, W), dtype=np.float64)
        padded[:h,:w] = secret_array.astype(np.float64)
        secret_wht = fwht_2d(padded)
        minv, maxv = secret_wht.min(), secret_wht.max()
        secret_scaled = ((secret_wht - minv)/(maxv - minv) * 255).astype(np.uint8)
        
        key = get_random_bytes(16)
        encrypted = encrypt_data(secret_scaled.flatten().tobytes(), key)
        
        stego_array = hide_data_in_image(cover, encrypted)
        stego_img = Image.fromarray(stego_array)
        
        stego_io = io.BytesIO()
        stego_img.save(stego_io, format='PNG')
        stego_io.seek(0)
        
        metadata = {"h": int(h), "w": int(w), "minv": float(minv), "maxv": float(maxv)}
        
        zip_io = io.BytesIO()
        with zipfile.ZipFile(zip_io, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('stego.png', stego_io.getvalue())

            key_io = io.BytesIO()
            np.save(key_io, np.frombuffer(key, dtype=np.uint8))
            zf.writestr('aes_key.npy', key_io.getvalue())
            zf.writestr('metadata.json', json.dumps(metadata))
            
        zip_io.seek(0)
        return send_file(zip_io, mimetype='application/zip', as_attachment=True, download_name='StegoVault_Data.zip')
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/extract', methods=['POST'])
def extract():
    try:
        stego_file = request.files['stego']
        key_file = request.files['key']
        meta_file = request.files['meta']
        
        stego_img = Image.open(stego_file).convert("RGB")
        key = np.load(key_file).tobytes()
        metadata = json.load(meta_file)
        
        h, w = metadata["h"], metadata["w"]
        minv, maxv = metadata["minv"], metadata["maxv"]
        H, W = next_pow2(h), next_pow2(w)
        
        data_length = H * W
        pad_len = 16 - (data_length % 16)
        encrypted_length = data_length + pad_len
        
        extracted = extract_data_from_image(stego_img, encrypted_length)
        decrypted = decrypt_data(extracted, key)
        
        recovered_flat = np.frombuffer(decrypted, dtype=np.uint8)
        recovered_scaled = recovered_flat.reshape((H,W))
        
        recovered_wht = recovered_scaled.astype(np.float64)/255*(maxv - minv) + minv
        recovered_img_array = np.clip(ifwht_2d(recovered_wht)[:h,:w], 0, 255).astype(np.uint8)
        recovered_img = Image.fromarray(recovered_img_array)
        
        img_io = io.BytesIO()
        recovered_img.save(img_io, format='PNG')
        img_io.seek(0)
        
        return send_file(img_io, mimetype='image/png', as_attachment=True, download_name='recovered_secret.png')

    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)