
#!/usr/bin/env python3
"""
BlogSphere - Local JSON file storage version
Uses JSON files in the data folder instead of database
"""

import os
import sys
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
class Config:
    DATA_FOLDER = 'data'
    SECRET_KEY = "secretkey"
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 60 * 1024 * 1024  # 60MB

# Initialize Flask app
app = Flask(__name__)
config = Config()
app.secret_key = config.SECRET_KEY
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH

# Create data and uploads directories
os.makedirs(config.DATA_FOLDER, exist_ok=True)
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

# File storage helper functions
def load_json_file(filename):
    """Load data from JSON file"""
    file_path = os.path.join(config.DATA_FOLDER, filename)
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error loading {filename}: {e}")
            return []
    return []

def save_json_file(filename, data):
    """Save data to JSON file"""
    file_path = os.path.join(config.DATA_FOLDER, filename)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception as e:
        logger.error(f"Error saving {filename}: {e}")
        return False

def get_next_id(data_list):
    """Get the next available ID"""
    if not data_list:
        return 1
    return max(item.get('id', 0) for item in data_list) + 1

# Simple User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, email, password_hash, is_admin=False, created_at=None):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.is_admin = is_admin
        self.created_at = created_at

# Login manager setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    try:
        users = load_json_file('Users.json')
        user_data = next((u for u in users if u['id'] == int(user_id)), None)
        
        if user_data:
            return User(
                user_data['id'], 
                user_data['username'], 
                user_data['email'], 
                user_data['password_hash'], 
                user_data.get('is_admin', False),
                user_data.get('created_at')
            )
        return None
    except Exception as e:
        logger.error(f"Error loading user: {e}")
        return None

# Template filter for JSON
@app.template_filter('from_json')
def from_json_filter(value):
    if value:
        try:
            if isinstance(value, str):
                return json.loads(value)
            return value
        except:
            return []
    return []

# Template filter for datetime formatting
@app.template_filter('format_datetime')
def format_datetime(value):
    if value:
        try:
            from datetime import datetime
            if isinstance(value, str):
                # Try to parse datetime string
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                return dt.strftime('%B %d, %Y at %I:%M %p') 
            elif hasattr(value, 'strftime'):
                # It's already a datetime object
                return value.strftime('%B %d, %Y at %I:%M %p')
            else:
                return str(value)
        except (ValueError, AttributeError):
            return str(value)
    return 'No date'

# Helper functions
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi', 'mov', 'wmv'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_posts():
    try:
        posts = load_json_file('Posts.json')
        users = load_json_file('Users.json')
        likes = load_json_file('likes.json')
        comments = load_json_file('Comments.json')
        
        # Create user lookup
        user_lookup = {u['id']: u for u in users}
        
        # Add additional data to posts
        enriched_posts = []
        for post in posts:
            # Get author info
            author = user_lookup.get(post['user_id'], {})
            
            # Count likes and comments
            like_count = len([l for l in likes if l['post_id'] == post['id']])
            comment_count = len([c for c in comments if c['post_id'] == post['id']])
            
            enriched_post = {
                'id': post['id'],
                'user_id': post['user_id'],
                'title': post['title'],
                'content': post['content'],
                'images': post.get('images'),
                'videos': post.get('videos'),
                'created_at': post['created_at'],
                'author': {'username': author.get('username', 'Unknown')},
                'like_count': like_count,
                'comment_count': comment_count
            }
            enriched_posts.append(enriched_post)
        
        # Sort by created_at (newest first)
        enriched_posts.sort(key=lambda x: x['created_at'], reverse=True)
        return enriched_posts
    except Exception as e:
        logger.error(f"Error getting posts: {e}")
        return []

# Routes
@app.route('/')
def index():
    posts = get_posts()
    return render_template('index.html', posts=posts)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        try:
            users = load_json_file('Users.json')
            
            # Check if username exists
            if any(u['username'] == username for u in users):
                flash('Username already exists', 'error')
                return redirect(url_for('register'))
            
            # Check if email exists
            if any(u['email'] == email for u in users):
                flash('Email already exists', 'error')
                return redirect(url_for('register'))
            
            # Create user
            password_hash = generate_password_hash(password)
            new_user = {
                'id': get_next_id(users),
                'username': username,
                'email': email,
                'password_hash': password_hash,
                'is_admin': False,
                'created_at': datetime.utcnow().isoformat()
            }
            
            users.append(new_user)
            save_json_file('Users.json', users)
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            logger.error(f"Registration error: {e}")
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            users = load_json_file('Users.json')
            user_data = next((u for u in users if u['username'] == username), None)
            
            if user_data and check_password_hash(user_data['password_hash'], password):
                user = User(
                    user_data['id'], 
                    user_data['username'], 
                    user_data['email'], 
                    user_data['password_hash'], 
                    user_data.get('is_admin', False),
                    user_data.get('created_at')
                )
                login_user(user)
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('index'))
            else:
                flash('Invalid username or password', 'error')
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            flash('Login failed. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        
        images = []
        videos = []
        
        if 'images' in request.files:
            for file in request.files.getlist('images'):
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    images.append(filename)
        
        if 'videos' in request.files:
            for file in request.files.getlist('videos'):
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    videos.append(filename)
        
        try:
            posts = load_json_file('Posts.json')
            new_post = {
                'id': get_next_id(posts),
                'user_id': current_user.id,
                'title': title,
                'content': content,
                'images': images if images else None,
                'videos': videos if videos else None,
                'created_at': datetime.utcnow().isoformat()
            }
            
            posts.append(new_post)
            save_json_file('Posts.json', posts)
            
            flash('Post created successfully!', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            logger.error(f"Create post error: {e}")
            flash('Failed to create post. Please try again.', 'error')
    
    return render_template('create_post.html')

@app.route('/post/<int:post_id>')
def post_detail(post_id):
    try:
        posts = load_json_file('Posts.json')
        users = load_json_file('Users.json')
        likes = load_json_file('likes.json')
        comments = load_json_file('Comments.json')
        
        # Find the post
        post_data = next((p for p in posts if p['id'] == post_id), None)
        if not post_data:
            flash('Post not found', 'error')
            return redirect(url_for('index'))
        
        # Get author info
        author = next((u for u in users if u['id'] == post_data['user_id']), {})
        
        # Count likes and comments
        like_count = len([l for l in likes if l['post_id'] == post_id])
        comment_count = len([c for c in comments if c['post_id'] == post_id])
        
        post = {
            'id': post_data['id'],
            'user_id': post_data['user_id'],
            'title': post_data['title'],
            'content': post_data['content'],
            'images': post_data.get('images'),
            'videos': post_data.get('videos'),
            'created_at': post_data['created_at'],
            'author': {
                'username': author.get('username', 'Unknown'),
                'created_at': author.get('created_at')
            },
            'like_count': like_count,
            'comment_count': comment_count
        }
        
        # Get comments with author info
        post_comments = []
        for comment in comments:
            if comment['post_id'] == post_id:
                comment_author = next((u for u in users if u['id'] == comment['user_id']), {})
                post_comments.append({
                    'id': comment['id'],
                    'user_id': comment['user_id'],
                    'content': comment['content'],
                    'created_at': comment['created_at'],
                    'author': {'username': comment_author.get('username', 'Unknown')}
                })
        
        # Sort comments by created_at
        post_comments.sort(key=lambda x: x['created_at'])
        
        return render_template('post_detail.html', post=post, comments=post_comments)
        
    except Exception as e:
        logger.error(f"Post detail error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        flash(f'Error loading post: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    try:
        likes = load_json_file('likes.json')
        
        # Check if already liked
        existing_like = next((l for l in likes if l['user_id'] == current_user.id and l['post_id'] == post_id), None)
        
        if existing_like:
            # Remove like
            likes = [l for l in likes if not (l['user_id'] == current_user.id and l['post_id'] == post_id)]
        else:
            # Add like
            new_like = {
                'id': get_next_id(likes),
                'user_id': current_user.id,
                'post_id': post_id,
                'created_at': datetime.utcnow().isoformat()
            }
            likes.append(new_like)
        
        save_json_file('likes.json', likes)
        
        # Redirect back to the post detail page
        return redirect(url_for('post_detail', post_id=post_id))
        
    except Exception as e:
        logger.error(f"Like post error: {e}")
        return jsonify({'error': 'Failed to like post'}), 500

@app.route('/comment/<int:post_id>', methods=['POST'])
@login_required
def add_comment(post_id):
    content = request.form['content']
    
    try:
        comments = load_json_file('Comments.json')
        new_comment = {
            'id': get_next_id(comments),
            'user_id': current_user.id,
            'post_id': post_id,
            'content': content,
            'created_at': datetime.utcnow().isoformat()
        }
        
        comments.append(new_comment)
        save_json_file('Comments.json', comments)
        
        flash('Comment added successfully!', 'success')
        
    except Exception as e:
        logger.error(f"Add comment error: {e}")
        flash('Failed to add comment', 'error')
    
    return redirect(url_for('post_detail', post_id=post_id))

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    try:
        users = load_json_file('Users.json')
        posts = load_json_file('Posts.json')
        
        stats = {
            'total_posts': len(posts),
            'total_users': len(users)
        }
        
        return render_template('admin_dashboard.html', users=users, posts=get_posts(), stats=stats)
        
    except Exception as e:
        logger.error(f"Admin dashboard error: {e}")
        flash('Error loading admin dashboard', 'error')
        return redirect(url_for('index'))

@app.route('/admin/delete_post/<int:post_id>', methods=['POST'])
@login_required
def admin_delete_post(post_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))

    try:
        # Delete likes related to this post
        likes = load_json_file('likes.json')
        likes = [l for l in likes if l['post_id'] != post_id]
        save_json_file('likes.json', likes)
        
        # Delete comments related to this post
        comments = load_json_file('Comments.json')
        comments = [c for c in comments if c['post_id'] != post_id]
        save_json_file('Comments.json', comments)
        
        # Delete the post
        posts = load_json_file('Posts.json')
        posts = [p for p in posts if p['id'] != post_id]
        save_json_file('Posts.json', posts)
        
        flash('Post deleted successfully!', 'success')

    except Exception as e:
        logger.error(f"Delete post error: {e}")
        flash('Failed to delete post.', 'error')

    return redirect(url_for('admin_dashboard'))

@app.route('/profile')
@login_required
def profile():
    try:
        posts = load_json_file('Posts.json')
        likes = load_json_file('likes.json')
        comments = load_json_file('Comments.json')
        
        # Filter posts by current user
        user_posts = []
        for post in posts:
            if post['user_id'] == current_user.id:
                like_count = len([l for l in likes if l['post_id'] == post['id']])
                comment_count = len([c for c in comments if c['post_id'] == post['id']])
                
                user_posts.append({
                    'id': post['id'],
                    'title': post['title'],
                    'content': post['content'],
                    'images': post.get('images'),
                    'videos': post.get('videos'),
                    'created_at': post['created_at'],
                    'like_count': like_count,
                    'comment_count': comment_count
                })
        
        # Sort by created_at (newest first)
        user_posts.sort(key=lambda x: x['created_at'], reverse=True)

        return render_template('profile.html', posts=user_posts)
        
    except Exception as e:
        logger.error(f"Profile error: {e}")
        flash('Error loading profile', 'error')
        return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def initialize_data():
    """Initialize data files and create admin user"""
    try:
        # Initialize empty files if they don't exist
        for filename in ['Users.json', 'Posts.json', 'Comments.json', 'likes.json']:
            file_path = os.path.join(config.DATA_FOLDER, filename)
            if not os.path.exists(file_path):
                save_json_file(filename, [])
        
        # Check if admin user exists
        users = load_json_file('Users.json')
        if not any(u['username'] == 'admin' for u in users):
            password_hash = generate_password_hash('admin123')
            admin_user = {
                'id': get_next_id(users),
                'username': 'admin',
                'email': 'admin@example.com',
                'password_hash': password_hash,
                'is_admin': True,
                'created_at': datetime.utcnow().isoformat()
            }
            users.append(admin_user)
            save_json_file('Users.json', users)
            logger.info('Admin user created: username=admin, password=admin123')
        
        logger.info('Data files initialized successfully')
        
    except Exception as e:
        logger.error(f"Data initialization error: {e}")
        raise

if __name__ == '__main__':
    try:
        initialize_data()
        logger.info('Starting BlogSphere application...')
        app.run(host='0.0.0.0', port=5000, debug=True)
        
    except Exception as e:
        logger.error(f'Failed to start application: {e}')
        sys.exit(1)
