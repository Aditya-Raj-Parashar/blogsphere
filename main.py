#!/usr/bin/env python3
"""
BlogSphere - PostgreSQL version
Modified to use PostgreSQL instead of MSSQL
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
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
class Config:
    # PostgreSQL configuration - using your public Railway URL
    DB_HOST = os.environ.get('DB_HOST', 'tramway.proxy.rlwy.net')
    DB_PORT = os.environ.get('DB_PORT', '10940')
    DB_NAME = os.environ.get('DB_NAME', 'railway')
    DB_USER = os.environ.get('DB_USER', 'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'skaKczsfSOyKrZKgFKqUcOBnqpdcXWoE')
    
    # Alternative: Use DATABASE_URL if provided
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:skaKczsfSOyKrZKgFKqUcOBnqpdcXWoE@tramway.proxy.rlwy.net:10940/railway')
    
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 60 * 1024 * 1024  # 60MB
    
    @property
    def connection_params(self):
        # If DATABASE_URL is provided, parse it
        if self.DATABASE_URL and self.DATABASE_URL.startswith('postgresql://'):
            import urllib.parse
            parsed = urllib.parse.urlparse(self.DATABASE_URL)
            return {
                'host': parsed.hostname,
                'port': parsed.port,
                'database': parsed.path[1:],  # Remove leading slash
                'user': parsed.username,
                'password': parsed.password
            }
        else:
            return {
                'host': self.DB_HOST,
                'port': self.DB_PORT,
                'database': self.DB_NAME,
                'user': self.DB_USER,
                'password': self.DB_PASSWORD
            }

# Initialize Flask app
app = Flask(__name__)
config = Config()
app.secret_key = config.SECRET_KEY
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH

# Create uploads directory
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

# Database connection helper
def get_db_connection():
    try:
        # Try to connect using the parsed connection parameters
        conn = psycopg2.connect(**config.connection_params)
        return conn
    except Exception as e:
        # If that fails, try connecting directly with the DATABASE_URL
        try:
            conn = psycopg2.connect(config.DATABASE_URL)
            return conn
        except Exception as e2:
            logger.error(f"Database connection failed with both methods:")
            logger.error(f"Method 1 error: {e}")
            logger.error(f"Method 2 error: {e2}")
            logger.error(f"Connection params: {config.connection_params}")
            raise e

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
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, password_hash, is_admin, created_at FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return User(row[0], row[1], row[2], row[3], row[4], row[5])
        return None
    except Exception as e:
        logger.error(f"Error loading user: {e}")
        return None

# Template filter for JSON
@app.template_filter('from_json')
def from_json_filter(value):
    if value:
        try:
            return json.loads(value)
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
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT p.id, p.user_id, p.title, p.content, p.images, p.videos, p.created_at,
                   u.username,
                   (SELECT COUNT(*) FROM likes WHERE post_id = p.id) as like_count,
                   (SELECT COUNT(*) FROM comments WHERE post_id = p.id) as comment_count
            FROM posts p 
            JOIN users u ON p.user_id = u.id 
            ORDER BY p.created_at DESC
        """)
        posts = []
        for row in cursor.fetchall():
            posts.append({
                'id': row['id'],
                'user_id': row['user_id'],
                'title': row['title'],
                'content': row['content'],
                'images': row['images'],
                'videos': row['videos'],
                'created_at': row['created_at'],
                'author': {'username': row['username']},
                'like_count': row['like_count'],
                'comment_count': row['comment_count']
            })
        conn.close()
        return posts
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
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check if username exists
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                flash('Username already exists', 'error')
                conn.close()
                return redirect(url_for('register'))
            
            # Check if email exists
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                flash('Email already exists', 'error')
                conn.close()
                return redirect(url_for('register'))
            
            # Create user
            password_hash = generate_password_hash(password)
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, is_admin, created_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (username, email, password_hash, False, datetime.utcnow()))
            
            conn.commit()
            conn.close()
            
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
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, email, password_hash, is_admin, created_at FROM users WHERE username = %s", (username,))
            row = cursor.fetchone()
            conn.close()
            
            if row and check_password_hash(row[3], password):
                user = User(row[0], row[1], row[2], row[3], row[4], row[5])
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
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO posts (user_id, title, content, images, videos, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (current_user.id, title, content, 
                  json.dumps(images) if images else None,
                  json.dumps(videos) if videos else None,
                  datetime.utcnow()))
            conn.commit()
            conn.close()
            
            flash('Post created successfully!', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            logger.error(f"Create post error: {e}")
            flash('Failed to create post. Please try again.', 'error')
    
    return render_template('create_post.html')

@app.route('/post/<int:post_id>')
def post_detail(post_id):
    try:
        logger.info(f"Loading post detail for post_id: {post_id}")
        conn = get_db_connection()
        cursor = conn.cursor()
        logger.info("Database connection established")
        
        # Get post details
        cursor.execute("""
            SELECT p.id, p.user_id, p.title, p.content, p.images, p.videos, p.created_at,
                   u.username, u.created_at as author_created_at,
                   (SELECT COUNT(*) FROM likes WHERE post_id = p.id) as like_count,
                   (SELECT COUNT(*) FROM comments WHERE post_id = p.id) as comment_count
            FROM posts p 
            JOIN users u ON p.user_id = u.id 
            WHERE p.id = %s
        """, (post_id,))
        post_row = cursor.fetchone()
        
        if not post_row:
            flash('Post not found', 'error')
            return redirect(url_for('index'))

        # Debug: Check what's in the images field
        logger.info(f"Post images field: {post_row[4]}")
        
        post = {
            'id': post_row[0],
            'user_id': post_row[1],
            'title': post_row[2],
            'content': post_row[3],
            'images': post_row[4],
            'videos': post_row[5],
            'created_at': post_row[6],
            'author': {'username': post_row[7], 'created_at': post_row[8]},
            'like_count': post_row[9],
            'comment_count': post_row[10]
        }
        
        # Get comments
        cursor.execute("""
            SELECT c.id, c.user_id, c.content, c.created_at, u.username
            FROM comments c
            JOIN users u ON c.user_id = u.id
            WHERE c.post_id = %s
            ORDER BY c.created_at ASC
        """, (post_id,))
        comments = []
        for row in cursor.fetchall():
            comments.append({
                'id': row[0],
                'user_id': row[1],
                'content': row[2],
                'created_at': row[3],
                'author': {'username': row[4]}
            })
        
        conn.close()
        return render_template('post_detail.html', post=post, comments=comments)
        
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
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if already liked
        cursor.execute("SELECT id FROM likes WHERE user_id = %s AND post_id = %s", (current_user.id, post_id))
        existing_like = cursor.fetchone()
        
        if existing_like:
            cursor.execute("DELETE FROM likes WHERE user_id = %s AND post_id = %s", (current_user.id, post_id))
            liked = False
        else:
            cursor.execute("INSERT INTO likes (user_id, post_id, created_at) VALUES (%s, %s, %s)", 
                          (current_user.id, post_id, datetime.utcnow()))
            liked = True
        
        conn.commit()
        
        # Get updated like count
        cursor.execute("SELECT COUNT(*) FROM likes WHERE post_id = %s", (post_id,))
        like_count = cursor.fetchone()[0]
        
        conn.close()
        
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
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO comments (user_id, post_id, content, created_at)
            VALUES (%s, %s, %s, %s)
        """, (current_user.id, post_id, content, datetime.utcnow()))
        conn.commit()
        conn.close()
        
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
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all users
        cursor.execute("SELECT id, username, email, is_admin, created_at FROM users")
        users = cursor.fetchall()

        # Get total posts
        cursor.execute("SELECT COUNT(*) FROM posts")
        total_posts = cursor.fetchone()[0]

        # Get total users
        total_users = len(users)

        conn.close()
        stats = {
            'total_posts': total_posts,
            'total_users': total_users
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
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First, delete likes related to this post
        cursor.execute("DELETE FROM likes WHERE post_id = %s", (post_id,))
        cursor.execute("DELETE FROM comments WHERE post_id = %s", (post_id,))
        
        # Then, delete the post
        cursor.execute("DELETE FROM posts WHERE id = %s", (post_id,))
        conn.commit()
        conn.close()
        
        flash('Post deleted successfully!', 'success')

    except Exception as e:
        logger.error(f"Delete post error: {e}")
        flash('Failed to delete post. It may be associated with existing likes.', 'error')

    return redirect(url_for('admin_dashboard'))

@app.route('/profile')
@login_required
def profile():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.title, p.content, p.images, p.videos, p.created_at,
                   (SELECT COUNT(*) FROM likes WHERE post_id = p.id) as like_count,
                   (SELECT COUNT(*) FROM comments WHERE post_id = p.id) as comment_count
            FROM posts p 
            WHERE p.user_id = %s
            ORDER BY p.created_at DESC
        """, (current_user.id,))
        posts = []
        for row in cursor.fetchall():
            posts.append({
                'id': row[0],
                'title': row[1],
                'content': row[2],
                'images': row[3],
                'videos': row[4],
                'created_at': row[5],
                'like_count': row[6],
                'comment_count': row[7]
            })
        conn.close()

        return render_template('profile.html', posts=posts)
        
    except Exception as e:
        logger.error(f"Profile error: {e}")
        flash('Error loading profile', 'error')
        return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def create_tables():
    """Create database tables if they don't exist"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(80) UNIQUE NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create posts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                title VARCHAR(200) NOT NULL,
                content TEXT NOT NULL,
                images TEXT,
                videos TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create likes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                post_id INTEGER REFERENCES posts(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, post_id)
            )
        """)
        
        # Create comments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                post_id INTEGER REFERENCES posts(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info('Database tables created successfully')
        
    except Exception as e:
        logger.error(f"Table creation error: {e}")
        raise

def initialize_database():
    """Initialize database and create admin user"""
    try:
        # Create tables first
        create_tables()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if admin user exists
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        if not cursor.fetchone():
            password_hash = generate_password_hash('admin123')
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, is_admin, created_at)
                VALUES (%s, %s, %s, %s, %s)
            """, ('admin', 'admin@example.com', password_hash, True, datetime.utcnow()))
            conn.commit()
            logger.info('Admin user created: username=admin, password=admin123')
        
        conn.close()
        logger.info('Database initialized successfully')
        
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise

if __name__ == '__main__':
    try:
        initialize_database()
        logger.info('Starting BlogSphere application...')
        app.run(host='0.0.0.0', port=5000, debug=True)
        
    except Exception as e:
        logger.error(f'Failed to start application: {e}')
        sys.exit(1)