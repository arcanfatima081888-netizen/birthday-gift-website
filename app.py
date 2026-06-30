# ============================================
# 1. IMPORTS
# ============================================
import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime
from PIL import Image
import io
import sys
import traceback

# ============================================
# 2. LOAD ENVIRONMENT VARIABLES
# ============================================
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Loaded .env file")
except ImportError:
    print("⚠️ python-dotenv not installed, using system environment variables")

# ============================================
# 3. FLASK APP INITIALIZATION
# ============================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# ============================================
# 4. CLOUDINARY CONFIGURATION
# ============================================
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')

print("\n" + "="*50)
print("📸 CLOUDINARY CONFIGURATION STATUS")
print("="*50)

if all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
    try:
        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET
        )
        print("✅ Cloudinary: CONFIGURED SUCCESSFULLY!")
        print(f"   Cloud Name: {CLOUDINARY_CLOUD_NAME}")
        CLOUDINARY_CONFIGURED = True
        
        try:
            cloudinary.api.ping()
            print("   Connection Test: ✅ PASSED")
        except Exception as e:
            print(f"   Connection Test: ⚠️ WARNING - {e}")
            
    except Exception as e:
        print(f"❌ Cloudinary configuration error: {e}")
        CLOUDINARY_CONFIGURED = False
else:
    print("⚠️ Cloudinary: NOT CONFIGURED")
    print("   Missing credentials - uploads will use local storage")
    CLOUDINARY_CONFIGURED = False

print("="*50 + "\n")

# ============================================
# 5. LOCAL STORAGE (FALLBACK)
# ============================================
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'mp4', 'mov', 'webm'}

try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    print(f"📁 Upload folder: {UPLOAD_FOLDER}")
except Exception as e:
    print(f"❌ Error creating upload folder: {e}")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ============================================
# 6. HELPER FUNCTIONS
# ============================================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def compress_image(file_data, max_size=(1200, 1200), quality=85):
    try:
        img = Image.open(io.BytesIO(file_data))
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        return output.getvalue()
    except Exception as e:
        print(f"❌ Error compressing image: {e}")
        return file_data

def upload_to_cloudinary(file_data, filename):
    if not CLOUDINARY_CONFIGURED:
        print("⚠️ Cloudinary not configured, saving locally instead")
        return save_file_locally(file_data, filename)
    
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
        public_id = f"birthday_gift_{timestamp}"
        
        print(f"📤 Uploading to Cloudinary: {filename}")
        print(f"   Public ID: {public_id}")
        
        upload_result = cloudinary.uploader.upload(
            file_data,
            public_id=public_id,
            resource_type="auto",
            folder="birthday_gift",
            use_filename=True,
            unique_filename=True
        )
        
        file_url = upload_result.get('secure_url')
        print(f"✅ Uploaded successfully: {file_url}")
        return file_url
        
    except Exception as e:
        print(f"❌ Cloudinary upload error: {e}")
        return save_file_locally(file_data, filename)

def save_file_locally(file_data, filename):
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
        unique_filename = f"{timestamp}_{secure_filename(filename)}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        with open(file_path, 'wb') as f:
            f.write(file_data)
        
        file_url = url_for('uploaded_file', filename=unique_filename)
        return file_url
    
    except Exception as e:
        print(f"❌ Error saving file locally: {e}")
        raise

def delete_from_cloudinary(public_id):
    if not CLOUDINARY_CONFIGURED:
        return delete_locally(public_id)
    
    try:
        result = cloudinary.uploader.destroy(public_id, resource_type="auto")
        return result.get('result') == 'ok'
    except Exception as e:
        print(f"❌ Error deleting from Cloudinary: {e}")
        return False

def delete_locally(filename):
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception as e:
        print(f"❌ Error deleting locally: {e}")
        return False

def get_cloudinary_files():
    """Get list of files from Cloudinary (with local fallback)"""
    if not CLOUDINARY_CONFIGURED:
        print("⚠️ Cloudinary not configured, using local files")
        return get_local_files()
    
    try:
        print("📸 Fetching files from Cloudinary...")
        
        # Get files with the birthday_gift prefix
        result = cloudinary.api.resources(
            type="upload",
            prefix="birthday_gift",
            resource_type="auto",
            max_results=100
        )
        
        files = []
        resources = result.get('resources', [])
        print(f"📸 Found {len(resources)} files in Cloudinary")
        
        for resource in resources:
            resource_type = resource.get('resource_type', 'image')
            format_type = resource.get('format', '')
            public_id = resource.get('public_id', '')
            created_at = resource.get('created_at', '')
            
            # Get the secure URL directly from Cloudinary
            url = resource.get('secure_url')
            
            print(f"   📄 {public_id}")
            
            # Extract filename from public_id
            filename = public_id.split('/')[-1] if '/' in public_id else public_id
            
            files.append({
                'url': url,  # Use the URL directly from Cloudinary
                'key': public_id,
                'filename': filename,
                'type': resource_type,
                'extension': format_type or 'jpg',
                'created_at': created_at
            })
        
        # Sort by created_at (newest first)
        files.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        print(f"✅ Retrieved {len(files)} files from Cloudinary")
        return files
        
    except Exception as e:
        print(f"❌ Error fetching from Cloudinary: {e}")
        print(traceback.format_exc())
        return get_local_files()

def get_local_files():
    files = []
    
    try:
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            return files
        
        uploaded_files = os.listdir(app.config['UPLOAD_FOLDER'])
        
        for filename in uploaded_files:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if not os.path.isfile(file_path):
                continue
            
            ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            if ext in {'jpg', 'jpeg', 'png', 'gif', 'webp'}:
                file_type = 'image'
            elif ext in {'mp4', 'mov', 'webm'}:
                file_type = 'video'
            else:
                file_type = 'other'
            
            file_url = url_for('uploaded_file', filename=filename)
            mod_time = os.path.getmtime(file_path)
            created_at = datetime.fromtimestamp(mod_time).isoformat()
            
            files.append({
                'url': file_url,
                'key': filename,
                'filename': filename,
                'type': file_type,
                'extension': ext,
                'created_at': created_at
            })
        
        files.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return files
    
    except Exception as e:
        print(f"❌ Error listing local files: {e}")
        return []

# ============================================
# 7. ROUTES
# ============================================

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        print(f"❌ Error serving file: {e}")
        return "File not found", 404

@app.route('/')
def home():
    return render_template('home.html', year=datetime.now().year)

@app.route('/gallery')
def gallery():
    print("="*50)
    print("📸 GALLERY PAGE LOADED")
    print("="*50)
    print(f"☁️ Cloudinary configured: {CLOUDINARY_CONFIGURED}")
    
    files = get_cloudinary_files()
    
    print(f"📸 Found {len(files)} files")
    if files:
        for i, file in enumerate(files[:5]):
            print(f"   File {i+1}: {file.get('filename')} - {file.get('type')}")
    print("="*50 + "\n")
    
    return render_template('gallery.html', files=files)

@app.route('/debug-gallery')
def debug_gallery():
    """Debug gallery to see what's happening"""
    if not CLOUDINARY_CONFIGURED:
        return "❌ Cloudinary is NOT configured!"
    
    try:
        result = cloudinary.api.resources(
            type="upload",
            prefix="birthday_gift",
            resource_type="auto",
            max_results=100
        )
        
        files = result.get('resources', [])
        
        html = """
        <html>
        <head>
            <title>Debug Gallery</title>
            <style>
                body { font-family: Arial; padding: 20px; background: #f5f0ff; }
                .file { background: white; margin: 10px 0; padding: 15px; border-radius: 5px; border: 1px solid #ddd; }
                img, video { max-width: 300px; border-radius: 5px; }
                .success { color: green; font-weight: bold; }
                .error { color: red; font-weight: bold; }
            </style>
        </head>
        <body>
            <h1>🔍 Debug Gallery</h1>
            <p><strong>Cloudinary Configured:</strong> ✅ Yes</p>
            <p><strong>Files Found:</strong> {len(files)}</p>
            <hr>
        """
        
        if files:
            for i, file in enumerate(files):
                public_id = file.get('public_id', '')
                resource_type = file.get('resource_type', '')
                url = file.get('secure_url', '')
                format_type = file.get('format', '')
                
                html += f"""
                <div class="file">
                    <h3>File #{i+1}</h3>
                    <p><strong>Public ID:</strong> {public_id}</p>
                    <p><strong>Type:</strong> {resource_type}</p>
                    <p><strong>Format:</strong> {format_type}</p>
                    <p><strong>URL:</strong> <a href="{url}" target="_blank">{url[:60]}...</a></p>
                    {'<img src="'+url+'" alt="'+public_id+'">' if resource_type == 'image' else ''}
                </div>
                """
        else:
            html += "<p class='error'>No files found with prefix 'birthday_gift'</p>"
        
        html += """
        <hr>
        <p><a href="/gallery">← Back to Gallery</a></p>
        </body>
        </html>
        """
        return html
        
    except Exception as e:
        return f"<h1 class='error'>Error: {e}</h1>"

@app.route('/message')
def message():
    return render_template('message.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        print("\n" + "="*50)
        print("📤 NEW UPLOAD ATTEMPT")
        print("="*50)
        
        if 'files' not in request.files:
            flash('No files selected', 'danger')
            return redirect(request.url)
        
        files = request.files.getlist('files')
        
        if not files or all(file.filename == '' for file in files):
            flash('No files selected', 'danger')
            return redirect(request.url)
        
        valid_files = [f for f in files if f.filename != '']
        
        if not valid_files:
            flash('No valid files selected', 'danger')
            return redirect(request.url)
        
        print(f"📄 Selected {len(valid_files)} files for upload")
        
        uploaded_count = 0
        failed_files = []
        
        for file in valid_files:
            try:
                print(f"\n📄 Processing: {file.filename}")
                
                file_data = file.read()
                
                if len(file_data) == 0:
                    failed_files.append(file.filename)
                    continue
                
                if not allowed_file(file.filename):
                    failed_files.append(file.filename)
                    continue
                
                filename = file.filename
                
                if filename.rsplit('.', 1)[1].lower() in {'jpg', 'jpeg', 'png', 'gif'}:
                    print("🔄 Compressing image...")
                    file_data = compress_image(file_data)
                    base_name = filename.rsplit('.', 1)[0]
                    filename = f"{base_name}.jpg"
                
                file_url = upload_to_cloudinary(file_data, filename)
                uploaded_count += 1
                print(f"✅ Uploaded: {filename}")
                
            except Exception as e:
                print(f"❌ Upload failed for {file.filename}: {e}")
                failed_files.append(file.filename)
        
        print("\n" + "="*50)
        print("📊 UPLOAD SUMMARY")
        print("="*50)
        print(f"✅ Successfully uploaded: {uploaded_count} files")
        if failed_files:
            print(f"❌ Failed: {len(failed_files)} files")
        print("="*50 + "\n")
        
        if uploaded_count > 0:
            if CLOUDINARY_CONFIGURED:
                flash(f'✅ {uploaded_count} file(s) uploaded successfully to Cloudinary! 🎉', 'success')
            else:
                flash(f'📁 {uploaded_count} file(s) saved locally! 🎉', 'success')
        
        if failed_files:
            flash(f'⚠️ {len(failed_files)} file(s) failed to upload.', 'warning')
        
        return redirect(url_for('gallery'))
    
    return render_template('upload.html')

@app.route('/delete/<path:file_key>', methods=['POST'])
def delete_file(file_key):
    if CLOUDINARY_CONFIGURED and file_key.startswith('birthday_gift'):
        success = delete_from_cloudinary(file_key)
    else:
        success = delete_locally(file_key)
    
    if success:
        flash('✅ File deleted successfully!', 'success')
    else:
        flash('❌ Failed to delete file', 'danger')
    
    return redirect(url_for('gallery'))

@app.route('/delete_all', methods=['POST'])
def delete_all_files():
    files = get_cloudinary_files()
    deleted_count = 0
    
    for file in files:
        file_key = file.get('key')
        if file_key:
            if CLOUDINARY_CONFIGURED and file_key.startswith('birthday_gift'):
                if delete_from_cloudinary(file_key):
                    deleted_count += 1
            else:
                if delete_locally(file_key):
                    deleted_count += 1
    
    if deleted_count > 0:
        flash(f'✅ Deleted {deleted_count} files successfully!', 'success')
    else:
        flash('No files to delete', 'info')
    
    return redirect(url_for('gallery'))

@app.errorhandler(413)
def too_large(e):
    flash('File too large. Maximum size is 50MB.', 'danger')
    return redirect(url_for('upload'))

# ============================================
# 8. RUN APP
# ============================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print("\n" + "="*50)
    print("🌈 BIRTHDAY GIFT WEBSITE 🌈")
    print("="*50)
    print(f"🚀 Running on: http://localhost:{port}")
    print(f"📁 Upload folder: {UPLOAD_FOLDER}")
    print(f"☁️ Cloudinary: {'✅ ENABLED' if CLOUDINARY_CONFIGURED else '⚠️ DISABLED'}")
    print("="*50 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)