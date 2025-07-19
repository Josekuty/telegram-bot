import os
import logging
import re
from flask import Flask, render_template, request, flash, send_file, redirect, url_for
import instaloader
from werkzeug.middleware.proxy_fix import ProxyFix
import tempfile
import shutil
import time
import subprocess
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Create downloads directory if it doesn't exist
DOWNLOADS_DIR = "downloads"
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

def validate_instagram_url(url):
    """Validate if the URL is a valid Instagram post or reel URL"""
    if not url:
        return False
    
    # Remove any trailing whitespace
    url = url.strip()
    
    # Check if it's a valid Instagram URL
    instagram_patterns = [
        r'https?://(?:www\.)?instagram\.com/(?:p|reel)/([A-Za-z0-9_-]+)',
        r'https?://(?:www\.)?instagram\.com/(?:p|reel)/([A-Za-z0-9_-]+)/',
    ]
    
    for pattern in instagram_patterns:
        if re.match(pattern, url):
            return True
    
    return False

def extract_shortcode(url):
    """Extract shortcode from Instagram URL"""
    try:
        # Handle different URL formats
        if "/p/" in url:
            shortcode = url.split("/p/")[1].split("/")[0].split("?")[0]
        elif "/reel/" in url:
            shortcode = url.split("/reel/")[1].split("/")[0].split("?")[0]
        else:
            return None
        
        return shortcode
    except Exception as e:
        logging.error(f"Error extracting shortcode: {e}")
        return None

def download_with_ytdlp(url, temp_dir):
    """Alternative download method using yt-dlp with anti-detection measures"""
    try:
        # Use yt-dlp with more aggressive anti-detection settings
        cmd = [
            'yt-dlp',
            url,
            '--output', f'{temp_dir}/%(title)s.%(ext)s',
            '--format', 'best[ext=mp4]/best',
            '--no-playlist',
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            '--referer', 'https://www.instagram.com/',
            '--add-header', 'Accept:text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            '--add-header', 'Accept-Language:en-US,en;q=0.5',
            '--add-header', 'Accept-Encoding:gzip, deflate, br',
            '--add-header', 'DNT:1',
            '--add-header', 'Connection:keep-alive',
            '--add-header', 'Upgrade-Insecure-Requests:1',
            '--sleep-interval', '1',
            '--max-sleep-interval', '3',
            '--extractor-retries', '3',
            '--fragment-retries', '3',
            '--retry-sleep', 'linear=2',
            '--ignore-errors'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            # Find the downloaded video file (mp4, webm, or other video formats)
            for file in os.listdir(temp_dir):
                if file.endswith(('.mp4', '.webm', '.mkv', '.avi')):
                    return os.path.join(temp_dir, file)
        else:
            logging.error(f"yt-dlp error: {result.stderr}")
            # Try to find any downloaded file even if command failed
            for file in os.listdir(temp_dir):
                if file.endswith(('.mp4', '.webm', '.mkv', '.avi')):
                    return os.path.join(temp_dir, file)
            
        return None
    except Exception as e:
        logging.error(f"yt-dlp download failed: {e}")
        return None

def download_instagram_content(url):
    """Download Instagram content using multiple methods with smart retry"""
    # Create temporary directory for this download
    temp_dir = tempfile.mkdtemp(dir=DOWNLOADS_DIR)
    
    # Smart retry with exponential backoff
    max_attempts = 3
    base_delay = 2
    
    for attempt in range(max_attempts):
        try:
            if attempt > 0:
                # Exponential backoff delay for retry attempts
                delay = base_delay * (2 ** (attempt - 1))
                logging.info(f"Retry attempt {attempt + 1} after {delay} seconds...")
                time.sleep(delay)
            
            # Method 1: Try yt-dlp first (more reliable)
            logging.info(f"Attempting download with yt-dlp (attempt {attempt + 1})...")
            video_file = download_with_ytdlp(url, temp_dir)
            
            if video_file and os.path.exists(video_file):
                logging.info("Successfully downloaded with yt-dlp")
                return video_file, None
            
            # Method 2: Fallback to instaloader if yt-dlp fails
            logging.info("yt-dlp failed, trying instaloader...")
            
            # Extract shortcode from URL
            shortcode = extract_shortcode(url)
            if not shortcode:
                continue  # Try again with next attempt
            
            # Create instaloader instance with settings to reduce detection
            loader = instaloader.Instaloader(
                download_videos=True,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=False,
                compress_json=False
            )
            
            # Set custom user agent to avoid detection
            try:
                loader.context._session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                })
            except:
                pass  # Ignore if headers can't be set
            
            # Add longer delay before request to avoid rate limiting
            time.sleep(5 + attempt * 2)  # Increase delay with each attempt
            
            # Get post from shortcode
            post = instaloader.Post.from_shortcode(loader.context, shortcode)
            
            # Download the post
            loader.download_post(post, target=temp_dir)
            
            # Find the downloaded video file (support multiple formats)
            video_file = None
            for file in os.listdir(temp_dir):
                if file.endswith(('.mp4', '.webm', '.mkv', '.avi')):
                    video_file = os.path.join(temp_dir, file)
                    break
            
            if video_file and os.path.exists(video_file):
                logging.info("Successfully downloaded with instaloader")
                return video_file, None
                
        except Exception as e:
            logging.error(f"Attempt {attempt + 1} failed: {e}")
            error_message = str(e).lower()
            
            # If this is the last attempt, return the error
            if attempt == max_attempts - 1:
                # Clean up temp directory on final error
                shutil.rmtree(temp_dir, ignore_errors=True)
                
                # Check if this is a rate limiting error
                if "403" in error_message or "401" in error_message or "rate" in error_message or "wait" in error_message:
                    return None, "I tried multiple times but Instagram is still blocking requests. The download should work automatically when their rate limit resets (usually 5-15 minutes)."
                else:
                    return None, f"Error downloading content after {max_attempts} attempts: {str(e)}"
            
            # Continue to next attempt
            continue
    
    # If we get here, all attempts failed
    shutil.rmtree(temp_dir, ignore_errors=True)
    return None, "All download attempts failed. Please try again later."

@app.route('/', methods=['GET', 'POST'])
def index():
    """Main route handling both form display and download processing"""
    
    if request.method == 'POST':
        # Get form data
        username = request.form.get('username', '').strip()
        instagram_url = request.form.get('instagram_url', '').strip()
        
        # Validate inputs
        if not username:
            flash('Please enter your name', 'error')
            return render_template('index.html')
        
        if not instagram_url:
            flash('Please enter an Instagram URL', 'error')
            return render_template('index.html', username=username)
        
        if not validate_instagram_url(instagram_url):
            flash('Please enter a valid Instagram post or reel URL', 'error')
            return render_template('index.html', username=username)
        
        # Attempt to download the content
        flash(f'Hi {username}! Processing your Instagram download...', 'info')
        
        try:
            video_file, error_message = download_instagram_content(instagram_url)
            
            if video_file:
                # Serve the file for download
                def cleanup_file():
                    """Clean up the temporary directory after sending file"""
                    try:
                        temp_dir = os.path.dirname(video_file)
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    except Exception as e:
                        logging.error(f"Error cleaning up file: {e}")
                
                # Schedule cleanup after file is sent
                response = send_file(
                    video_file,
                    as_attachment=True,
                    download_name=f"instagram_download_{extract_shortcode(instagram_url)}.mp4",
                    mimetype='video/mp4'
                )
                
                # Clean up the file after sending
                cleanup_file()
                
                return response
            else:
                flash(f'Sorry {username}, {error_message}', 'error')
                return render_template('index.html', username=username)
                
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            flash(f'Sorry {username}, an unexpected error occurred: {str(e)}', 'error')
            return render_template('index.html', username=username)
    
    # GET request - show the form
    return render_template('index.html')

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return {'status': 'healthy', 'service': 'Instagram Downloader'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
