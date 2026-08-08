# ============================================================
# YASH WORLD - Complete Firebase Firestore Version
# ============================================================

import os
import json
import logging
import requests
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import base64
import firebase_admin
from firebase_admin import credentials, firestore, auth

# ============================================================
# LOGGING CONFIGURATION
# ============================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# APP CREATION
# ============================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'yash-world-secret-key-2024')

# ============================================================
# FIREBASE CONFIGURATION
# ============================================================

# Get project ID from environment or use default
FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'happybirthday-a287a')

# Initialize Firebase
db = None
try:
    # Option 1: Using service account JSON file (local development)
    if os.path.exists('service-account.json'):
        cred = credentials.Certificate('service-account.json')
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        logger.info("✅ Firebase initialized with service account file")
    
    # Option 2: Using environment variables (Render deployment)
    elif os.environ.get('FIREBASE_PRIVATE_KEY'):
        # Get the private key and handle newlines properly
        private_key = os.environ.get('FIREBASE_PRIVATE_KEY')
        # Replace literal \n with actual newlines if needed
        if '\\n' in private_key:
            private_key = private_key.replace('\\n', '\n')
        
        firebase_config = {
            "type": "service_account",
            "project_id": FIREBASE_PROJECT_ID,
            "private_key_id": os.environ.get('FIREBASE_PRIVATE_KEY_ID', ''),
            "private_key": private_key,
            "client_email": os.environ.get('FIREBASE_CLIENT_EMAIL'),
            "client_id": os.environ.get('FIREBASE_CLIENT_ID', ''),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.environ.get('FIREBASE_CLIENT_CERT_URL', '')
        }
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        logger.info("✅ Firebase initialized with environment variables")
    
    # Option 3: Using credentials JSON from environment variable
    elif os.environ.get('FIREBASE_CREDENTIALS_JSON'):
        creds_json = json.loads(os.environ.get('FIREBASE_CREDENTIALS_JSON'))
        cred = credentials.Certificate(creds_json)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        logger.info("✅ Firebase initialized with credentials JSON")
    
    else:
        # Option 4: Using mock data (for testing)
        logger.warning("⚠️ No Firebase credentials found. Using mock data.")
        db = None

except Exception as e:
    logger.error(f"❌ Firebase initialization error: {e}")
    db = None

# ============================================================
# USER STORE (Fallback if Firebase not available)
# ============================================================

USERS = {}

def init_local_users():
    """Initialize local users if Firebase is not available"""
    if not USERS:
        USERS['yash'] = {
            'password_hash': generate_password_hash('admin123'),
            'is_admin': True,
            'is_friend': True,
            'created_at': datetime.utcnow().isoformat()
        }
        USERS['Glory'] = {
            'password_hash': generate_password_hash('lory'),
            'is_admin': False,
            'is_friend': True,
            'created_at': datetime.utcnow().isoformat()
        }
        logger.info("✅ Local users initialized")

# ============================================================
# FIREBASE DATABASE HELPERS
# ============================================================

def get_user_from_firebase(username):
    """Get user from Firebase Firestore"""
    if not db:
        return None
    try:
        users_ref = db.collection('users')
        query = users_ref.where('username', '==', username).limit(1).get()
        for doc in query:
            user_data = doc.to_dict()
            user_data['id'] = doc.id
            return user_data
        return None
    except Exception as e:
        logger.error(f"Error getting user from Firebase: {e}")
        return None

def save_user_to_firebase(username, user_data):
    """Save user to Firebase Firestore"""
    if not db:
        return None
    try:
        doc_ref = db.collection('users').document()
        doc_ref.set(user_data)
        user_data['id'] = doc_ref.id
        return user_data
    except Exception as e:
        logger.error(f"Error saving user to Firebase: {e}")
        return None

def get_questions_from_firebase():
    """Get all questions from Firebase Firestore"""
    if not db:
        return []
    try:
        questions_ref = db.collection('questions').order_by('created_at', direction=firestore.Query.DESCENDING)
        docs = questions_ref.stream()
        questions = []
        for doc in docs:
            q_data = doc.to_dict()
            q_data['id'] = doc.id
            # Get replies for this question
            replies_ref = db.collection('replies').where('question_id', '==', doc.id).order_by('created_at')
            reply_docs = replies_ref.stream()
            replies = []
            for r_doc in reply_docs:
                r_data = r_doc.to_dict()
                r_data['id'] = r_doc.id
                replies.append(r_data)
            q_data['replies'] = replies
            questions.append(q_data)
        return questions
    except Exception as e:
        logger.error(f"Error getting questions from Firebase: {e}")
        return []

def save_question_to_firebase(question_data):
    """Save question to Firebase Firestore"""
    if not db:
        return None
    try:
        doc_ref = db.collection('questions').document()
        doc_ref.set(question_data)
        question_data['id'] = doc_ref.id
        return question_data
    except Exception as e:
        logger.error(f"Error saving question to Firebase: {e}")
        return None

def get_question_from_firebase(question_id):
    """Get a single question from Firebase Firestore"""
    if not db:
        return None
    try:
        doc_ref = db.collection('questions').document(question_id)
        doc = doc_ref.get()
        if doc.exists:
            q_data = doc.to_dict()
            q_data['id'] = doc.id
            # Get replies
            replies_ref = db.collection('replies').where('question_id', '==', question_id).order_by('created_at')
            reply_docs = replies_ref.stream()
            replies = []
            for r_doc in reply_docs:
                r_data = r_doc.to_dict()
                r_data['id'] = r_doc.id
                replies.append(r_data)
            q_data['replies'] = replies
            return q_data
        return None
    except Exception as e:
        logger.error(f"Error getting question from Firebase: {e}")
        return None

def save_reply_to_firebase(question_id, reply_data):
    """Save reply to Firebase Firestore"""
    if not db:
        return None
    try:
        doc_ref = db.collection('replies').document()
        doc_ref.set(reply_data)
        reply_data['id'] = doc_ref.id
        # Update question's is_answered status
        db.collection('questions').document(question_id).update({
            'is_answered': True,
            'updated_at': datetime.utcnow().isoformat()
        })
        return reply_data
    except Exception as e:
        logger.error(f"Error saving reply to Firebase: {e}")
        return None

def get_typing_text_from_firebase():
    """Get active typing text from Firebase Firestore"""
    if not db:
        return None
    try:
        docs = db.collection('typing_texts').where('is_active', '==', True).limit(1).stream()
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None
    except Exception as e:
        logger.error(f"Error getting typing text from Firebase: {e}")
        return None

# ============================================================
# COMBINED USER FUNCTIONS (Firebase + Local Fallback)
# ============================================================

def get_user(username):
    """Get user from Firebase or local fallback"""
    if db:
        user = get_user_from_firebase(username)
        if user:
            return user
    # Fallback to local
    if username in USERS:
        user_data = USERS[username].copy()
        user_data['id'] = username
        return user_data
    return None

def get_user_by_id(user_id):
    """Get user by ID"""
    if db:
        try:
            doc_ref = db.collection('users').document(user_id)
            doc = doc_ref.get()
            if doc.exists:
                user_data = doc.to_dict()
                user_data['id'] = doc.id
                return user_data
        except:
            pass
    # Fallback to local
    if user_id in USERS:
        user_data = USERS[user_id].copy()
        user_data['id'] = user_id
        return user_data
    return None

def get_all_users():
    """Get all users"""
    users = []
    if db:
        try:
            docs = db.collection('users').stream()
            for doc in docs:
                user_data = doc.to_dict()
                user_data['id'] = doc.id
                users.append(user_data)
        except:
            pass
    # Add local users if not already added
    for username, data in USERS.items():
        if not any(u.get('username') == username for u in users):
            user_data = data.copy()
            user_data['id'] = username
            user_data['username'] = username
            users.append(user_data)
    return users

def get_questions():
    """Get questions from Firebase or local"""
    if db:
        questions = get_questions_from_firebase()
        if questions:
            return questions
    return []  # Return empty if no questions

def create_question(question_data):
    """Create question in Firebase or local"""
    if db:
        return save_question_to_firebase(question_data)
    # Local fallback - store in memory
    return None

def get_question(question_id):
    """Get question from Firebase or local"""
    if db:
        return get_question_from_firebase(question_id)
    return None

def add_reply(question_id, reply_data):
    """Add reply in Firebase or local"""
    if db:
        return save_reply_to_firebase(question_id, reply_data)
    return None

def get_typing_text():
    """Get typing text from Firebase or local"""
    if db:
        return get_typing_text_from_firebase()
    return None

# ============================================================
# USER CLASS FOR FLASK-LOGIN
# ============================================================

class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data.get('id')
        self.username = user_data.get('username')
        self.password_hash = user_data.get('password_hash')
        self.is_admin = user_data.get('is_admin', False)
        self.is_friend = user_data.get('is_friend', False)
        self.created_at = user_data.get('created_at')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# ============================================================
# LOGIN MANAGER
# ============================================================

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    user_data = get_user_by_id(user_id)
    if user_data:
        return User(user_data)
    return None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You need admin access for this page.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================================
# CONTEXT PROCESSOR
# ============================================================

@app.context_processor
def utility_processor():
    def get_site_settings():
        return {
            'site_title': 'YASH WORLD',
            'site_tagline': 'Private Messaging Platform'
        }
    return dict(get_site_settings=get_site_settings)

# ============================================================
# MEDIA HELPERS
# ============================================================

ALLOWED_IMAGES = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_VIDEOS = {'mp4', 'webm', 'mov', 'avi', 'mkv'}
ALLOWED_AUDIO = {'mp3', 'wav', 'ogg', 'm4a', 'aac', 'flac'}

def get_file_extension(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

def is_allowed_image(filename):
    return get_file_extension(filename) in ALLOWED_IMAGES

def is_allowed_video(filename):
    return get_file_extension(filename) in ALLOWED_VIDEOS

def is_allowed_audio(filename):
    return get_file_extension(filename) in ALLOWED_AUDIO

def file_to_base64(file):
    if file and file.filename:
        try:
            file_data = file.read()
            base64_data = base64.b64encode(file_data).decode('utf-8')
            return base64_data
        except Exception as e:
            logger.error(f"Error converting file to base64: {e}")
            return None
    return None

# ============================================================
# ROUTES - AUTHENTICATION
# ============================================================

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        
        user_data = get_user(username)
        if user_data:
            user = User(user_data)
            if user.check_password(password):
                login_user(user, remember=remember)
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
        
        flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# ============================================================
# ROUTES - DATABASE STATUS CHECK
# ============================================================

@app.route('/db-status')
def db_status():
    """Check database connection status"""
    if db:
        try:
            # Try to read from Firebase to verify connection
            db.collection('users').limit(1).get()
            return jsonify({
                'status': 'connected',
                'database': 'Firebase Firestore',
                'project': FIREBASE_PROJECT_ID,
                'message': '✅ Database is connected and working!'
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': str(e),
                'message': '❌ Database connection failed'
            }), 500
    else:
        return jsonify({
            'status': 'disconnected',
            'message': '⚠️ Firebase not initialized. Using mock data.'
        }), 503

# ============================================================
# ROUTES - DASHBOARD
# ============================================================

@app.route('/dashboard')
@login_required
def dashboard():
    questions = get_questions()
    is_admin = current_user.is_admin
    is_friend = current_user.is_friend
    
    typing_text = None
    show_typing = False
    
    if is_friend and not is_admin:
        seen_typing = session.get('seen_typing_' + str(current_user.id), False)
        if not seen_typing:
            show_typing = True
            typing_text = get_typing_text()
            if not typing_text:
                typing_text = {'text': 'Welcome to YASH WORLD! 🌟\nThis is a private messaging platform.\nAsk questions and get replies from your friend.'}
    
    current_index = session.get('current_question_index', 0)
    
    if not questions:
        return render_template('dashboard.html', 
            questions=[],
            current_question=None,
            current_index=0,
            total_questions=0,
            is_admin=is_admin,
            is_friend=is_friend,
            current_user=current_user,
            feedback_questions=[],
            typing_text=typing_text,
            show_typing=show_typing
        )
    
    if current_index >= len(questions):
        current_index = 0
        session['current_question_index'] = 0
    
    current_question = questions[current_index]
    total_questions = len(questions)
    
    return render_template('dashboard.html', 
        questions=questions,
        current_question=current_question,
        current_index=current_index,
        total_questions=total_questions,
        replies=current_question.get('replies', []),
        is_admin=is_admin,
        is_friend=is_friend,
        current_user=current_user,
        feedback_questions=[],
        typing_text=typing_text,
        show_typing=show_typing
    )

# ============================================================
# ROUTES - NAVIGATE QUESTIONS
# ============================================================

@app.route('/navigate-question', methods=['POST'])
@login_required
def navigate_question():
    direction = request.form.get('direction')
    current_index = session.get('current_question_index', 0)
    questions = get_questions()
    total_questions = len(questions)
    
    if direction == 'next':
        current_index = min(current_index + 1, total_questions - 1)
    elif direction == 'prev':
        current_index = max(current_index - 1, 0)
    
    session['current_question_index'] = current_index
    return redirect(url_for('dashboard'))

# ============================================================
# ROUTES - SEEN TYPING
# ============================================================

@app.route('/seen-typing', methods=['POST'])
@login_required
def seen_typing():
    session['seen_typing_' + str(current_user.id)] = True
    return jsonify({'success': True})

# ============================================================
# ROUTES - ASK QUESTION
# ============================================================

@app.route('/ask', methods=['GET', 'POST'])
@login_required
def ask_question():
    if not current_user.is_admin:
        flash('Only admin can ask questions.', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        text = request.form.get('text', '').strip()
        
        if not text:
            flash('Please enter a question.', 'danger')
            return redirect(url_for('ask_question'))
        
        question_data = {
            'user_id': current_user.id,
            'username': current_user.username,
            'text': text,
            'image_data': None,
            'video_data': None,
            'audio_data': None,
            'image_filename': None,
            'video_filename': None,
            'audio_filename': None,
            'answer_text': None,
            'answer_image_data': None,
            'answer_video_data': None,
            'answer_audio_data': None,
            'answer_image_filename': None,
            'answer_video_filename': None,
            'answer_audio_filename': None,
            'has_answer': False,
            'is_answered': False,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        if 'image' in request.files and request.files['image'].filename:
            file = request.files['image']
            if is_allowed_image(file.filename):
                question_data['image_data'] = file_to_base64(file)
                question_data['image_filename'] = secure_filename(file.filename)
        
        if 'video' in request.files and request.files['video'].filename:
            file = request.files['video']
            if is_allowed_video(file.filename):
                question_data['video_data'] = file_to_base64(file)
                question_data['video_filename'] = secure_filename(file.filename)
        
        if 'audio' in request.files and request.files['audio'].filename:
            file = request.files['audio']
            if is_allowed_audio(file.filename):
                question_data['audio_data'] = file_to_base64(file)
                question_data['audio_filename'] = secure_filename(file.filename)
        
        answer_text = request.form.get('answer_text', '').strip()
        if answer_text:
            question_data['answer_text'] = answer_text
            question_data['has_answer'] = True
            question_data['is_answered'] = True
            
            if 'answer_image' in request.files and request.files['answer_image'].filename:
                file = request.files['answer_image']
                if is_allowed_image(file.filename):
                    question_data['answer_image_data'] = file_to_base64(file)
                    question_data['answer_image_filename'] = secure_filename(file.filename)
            
            if 'answer_video' in request.files and request.files['answer_video'].filename:
                file = request.files['answer_video']
                if is_allowed_video(file.filename):
                    question_data['answer_video_data'] = file_to_base64(file)
                    question_data['answer_video_filename'] = secure_filename(file.filename)
            
            if 'answer_audio' in request.files and request.files['answer_audio'].filename:
                file = request.files['answer_audio']
                if is_allowed_audio(file.filename):
                    question_data['answer_audio_data'] = file_to_base64(file)
                    question_data['answer_audio_filename'] = secure_filename(file.filename)
        
        question = create_question(question_data)
        if question:
            flash('Question asked successfully!' + (' Answer added!' if answer_text else ''), 'success')
        else:
            flash('Error creating question. Please try again.', 'danger')
        
        return redirect(url_for('dashboard'))
    
    return render_template('ask.html')

# ============================================================
# ROUTES - REPLY TO QUESTION
# ============================================================

@app.route('/reply/<question_id>', methods=['GET', 'POST'])
@login_required
def reply_question(question_id):
    question = get_question(question_id)
    
    if not question:
        flash('Question not found.', 'danger')
        return redirect(url_for('dashboard'))
    
    if not current_user.is_friend and not current_user.is_admin:
        flash('Only friend can reply.', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        text = request.form.get('text', '').strip()
        
        if not text:
            flash('Please enter a reply.', 'danger')
            return redirect(url_for('reply_question', question_id=question_id))
        
        reply_data = {
            'question_id': question_id,
            'user_id': current_user.id,
            'username': current_user.username,
            'text': text,
            'image_data': None,
            'video_data': None,
            'audio_data': None,
            'image_filename': None,
            'video_filename': None,
            'audio_filename': None,
            'created_at': datetime.utcnow().isoformat()
        }
        
        if 'image' in request.files and request.files['image'].filename:
            file = request.files['image']
            if is_allowed_image(file.filename):
                reply_data['image_data'] = file_to_base64(file)
                reply_data['image_filename'] = secure_filename(file.filename)
        
        if 'video' in request.files and request.files['video'].filename:
            file = request.files['video']
            if is_allowed_video(file.filename):
                reply_data['video_data'] = file_to_base64(file)
                reply_data['video_filename'] = secure_filename(file.filename)
        
        if 'audio' in request.files and request.files['audio'].filename:
            file = request.files['audio']
            if is_allowed_audio(file.filename):
                reply_data['audio_data'] = file_to_base64(file)
                reply_data['audio_filename'] = secure_filename(file.filename)
        
        reply = add_reply(question_id, reply_data)
        if reply:
            flash('Reply sent successfully!', 'success')
        else:
            flash('Error saving reply. Please try again.', 'danger')
        
        return redirect(url_for('dashboard'))
    
    return render_template('reply.html', question=question)

# ============================================================
# ROUTES - DELETE QUESTION & REPLY
# ============================================================

@app.route('/question/<question_id>/delete', methods=['POST'])
@login_required
def delete_question(question_id):
    if not current_user.is_admin:
        flash('Only admin can delete questions.', 'danger')
        return redirect(url_for('dashboard'))
    
    if db:
        try:
            # Delete replies first
            replies_ref = db.collection('replies').where('question_id', '==', question_id)
            for doc in replies_ref.stream():
                doc.reference.delete()
            # Delete question
            db.collection('questions').document(question_id).delete()
            flash('Question deleted successfully!', 'success')
        except Exception as e:
            logger.error(f"Error deleting question: {e}")
            flash('Error deleting question.', 'danger')
    else:
        flash('Database not connected.', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/reply/<question_id>/<reply_id>/delete', methods=['POST'])
@login_required
def delete_reply(question_id, reply_id):
    if not current_user.is_admin:
        flash('Only admin can delete replies.', 'danger')
        return redirect(url_for('dashboard'))
    
    if db:
        try:
            db.collection('replies').document(reply_id).delete()
            flash('Reply deleted successfully!', 'success')
        except Exception as e:
            logger.error(f"Error deleting reply: {e}")
            flash('Error deleting reply.', 'danger')
    else:
        flash('Database not connected.', 'danger')
    
    return redirect(url_for('dashboard'))

# ============================================================
# ROUTES - ADMIN USERS
# ============================================================

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = get_all_users()
    return render_template('admin_users.html', users=users)

@app.route('/admin/user/<user_id>/toggle-friend', methods=['POST'])
@login_required
@admin_required
def toggle_friend(user_id):
    if db:
        try:
            doc_ref = db.collection('users').document(user_id)
            doc = doc_ref.get()
            if doc.exists:
                user_data = doc.to_dict()
                new_status = not user_data.get('is_friend', False)
                doc_ref.update({'is_friend': new_status})
                status = 'enabled' if new_status else 'disabled'
                flash(f'Friend access {status} for {user_data.get("username")}', 'success')
            else:
                flash('User not found.', 'danger')
        except Exception as e:
            logger.error(f"Error toggling friend: {e}")
            flash('Error updating user.', 'danger')
    else:
        flash('Database not connected.', 'danger')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<user_id>/reset-typing', methods=['POST'])
@login_required
@admin_required
def reset_typing(user_id):
    session.pop('seen_typing_' + str(user_id), None)
    flash('Typing animation reset for user.', 'success')
    return redirect(url_for('admin_users'))

# ============================================================
# ROUTES - TYPING TEXT ADMIN
# ============================================================

@app.route('/admin/typing-text', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_typing_text():
    if request.method == 'POST':
        text = request.form.get('typing_text', '').strip()
        if text and db:
            try:
                # Deactivate all existing
                docs = db.collection('typing_texts').stream()
                for doc in docs:
                    doc.reference.update({'is_active': False})
                
                # Add new active text
                doc_ref = db.collection('typing_texts').document()
                doc_ref.set({
                    'text': text,
                    'is_active': True,
                    'created_at': datetime.utcnow().isoformat(),
                    'updated_at': datetime.utcnow().isoformat()
                })
                flash('Typing text updated successfully!', 'success')
            except Exception as e:
                logger.error(f"Error saving typing text: {e}")
                flash('Error saving typing text.', 'danger')
        else:
            flash('Please enter some text.', 'danger')
        return redirect(url_for('admin_typing_text'))
    
    typing_texts = []
    active_text = None
    
    if db:
        try:
            docs = db.collection('typing_texts').order_by('created_at', direction=firestore.Query.DESCENDING).stream()
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                typing_texts.append(data)
        except Exception as e:
            logger.error(f"Error getting typing texts: {e}")
        
        try:
            docs = db.collection('typing_texts').where('is_active', '==', True).limit(1).stream()
            for doc in docs:
                active_text = doc.to_dict()
                active_text['id'] = doc.id
        except Exception as e:
            logger.error(f"Error getting active typing text: {e}")
    
    return render_template('admin_typing_text.html', 
        typing_texts=typing_texts,
        active_text=active_text
    )

@app.route('/admin/typing-text/<text_id>/activate')
@login_required
@admin_required
def admin_activate_typing_text(text_id):
    if db:
        try:
            # Deactivate all
            docs = db.collection('typing_texts').stream()
            for doc in docs:
                doc.reference.update({'is_active': False})
            
            # Activate selected
            db.collection('typing_texts').document(text_id).update({
                'is_active': True,
                'updated_at': datetime.utcnow().isoformat()
            })
            flash('Typing text activated!', 'success')
        except Exception as e:
            logger.error(f"Error activating typing text: {e}")
            flash('Error activating typing text.', 'danger')
    
    return redirect(url_for('admin_typing_text'))

@app.route('/admin/typing-text/<text_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_typing_text(text_id):
    if db:
        try:
            db.collection('typing_texts').document(text_id).delete()
            flash('Typing text deleted!', 'success')
        except Exception as e:
            logger.error(f"Error deleting typing text: {e}")
            flash('Error deleting typing text.', 'danger')
    
    return redirect(url_for('admin_typing_text'))

# ============================================================
# ROUTES - SETTINGS
# ============================================================

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_settings():
    settings = {'site_title': 'YASH WORLD', 'site_tagline': 'Private Messaging Platform'}
    
    if db:
        settings_ref = db.collection('settings').document('site_settings')
        
        if request.method == 'POST':
            try:
                settings_ref.update({
                    'site_title': request.form.get('site_title', 'YASH WORLD'),
                    'site_tagline': request.form.get('site_tagline', 'Private Messaging Platform'),
                    'welcome_message': request.form.get('welcome_message', '')
                })
                flash('Settings updated successfully!', 'success')
            except Exception as e:
                logger.error(f"Error updating settings: {e}")
                flash('Error updating settings.', 'danger')
            return redirect(url_for('admin_settings'))
        
        doc = settings_ref.get()
        if doc.exists:
            settings = doc.to_dict()
    
    return render_template('admin_settings.html', settings=settings)

# ============================================================
# ROUTES - FEEDBACK
# ============================================================

@app.route('/admin/feedback')
@login_required
@admin_required
def admin_feedback():
    return render_template('admin_feedback.html', questions=[], responses=[])

@app.route('/admin/responses')
@login_required
@admin_required
def admin_responses():
    return render_template('admin_responses.html',
        all_replies=[],
        total_replies=0,
        unique_questions=0,
        total_questions=0,
        completion_percentage=0
    )

# ============================================================
# ROUTES - MEDIA SERVE
# ============================================================

@app.route('/media/question/image/<question_id>')
def question_image(question_id):
    question = get_question(question_id)
    if question and question.get('image_data'):
        return question['image_data'], 200, {'Content-Type': 'image/jpeg'}
    return '', 404

@app.route('/media/question/video/<question_id>')
def question_video(question_id):
    question = get_question(question_id)
    if question and question.get('video_data'):
        return question['video_data'], 200, {'Content-Type': 'video/mp4'}
    return '', 404

@app.route('/media/question/audio/<question_id>')
def question_audio(question_id):
    question = get_question(question_id)
    if question and question.get('audio_data'):
        return question['audio_data'], 200, {'Content-Type': 'audio/mpeg'}
    return '', 404

@app.route('/media/reply/image/<question_id>/<reply_id>')
def reply_image(question_id, reply_id):
    question = get_question(question_id)
    if question and 'replies' in question:
        for reply in question['replies']:
            if str(reply.get('id')) == str(reply_id) and reply.get('image_data'):
                return reply['image_data'], 200, {'Content-Type': 'image/jpeg'}
    return '', 404

@app.route('/media/reply/video/<question_id>/<reply_id>')
def reply_video(question_id, reply_id):
    question = get_question(question_id)
    if question and 'replies' in question:
        for reply in question['replies']:
            if str(reply.get('id')) == str(reply_id) and reply.get('video_data'):
                return reply['video_data'], 200, {'Content-Type': 'video/mp4'}
    return '', 404

@app.route('/media/reply/audio/<question_id>/<reply_id>')
def reply_audio(question_id, reply_id):
    question = get_question(question_id)
    if question and 'replies' in question:
        for reply in question['replies']:
            if str(reply.get('id')) == str(reply_id) and reply.get('audio_data'):
                return reply['audio_data'], 200, {'Content-Type': 'audio/mpeg'}
    return '', 404

# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', error_code=404, message='Page not found'), 404

@app.errorhandler(500)
def server_error(error):
    return render_template('error.html', error_code=500, message='Internal server error'), 500

# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():
    """Initialize Firebase with default data"""
    init_local_users()
    
    if db:
        try:
            # Check if admin exists
            admin = get_user('yash')
            if not admin:
                admin_data = {
                    'username': 'yash',
                    'password_hash': generate_password_hash('admin123'),
                    'is_admin': True,
                    'is_friend': True,
                    'created_at': datetime.utcnow().isoformat()
                }
                doc_ref = db.collection('users').document()
                doc_ref.set(admin_data)
                logger.info("✅ Admin user created in Firebase: yash / admin123")
            else:
                logger.info("✅ Admin user already exists in Firebase")
            
            # Check if friend exists
            friend = get_user('Glory')
            if not friend:
                friend_data = {
                    'username': 'Glory',
                    'password_hash': generate_password_hash('lory'),
                    'is_admin': False,
                    'is_friend': True,
                    'created_at': datetime.utcnow().isoformat()
                }
                doc_ref = db.collection('users').document()
                doc_ref.set(friend_data)
                logger.info("✅ Friend user created in Firebase: Glory / lory")
            else:
                logger.info("✅ Friend user already exists in Firebase")
            
            # Create default settings
            settings_ref = db.collection('settings').document('site_settings')
            if not settings_ref.get().exists:
                settings_ref.set({
                    'site_title': 'YASH WORLD',
                    'site_tagline': 'Private Messaging & QA Platform',
                    'welcome_message': ''
                })
                logger.info("✅ Default settings created in Firebase")
            
            logger.info("\n" + "="*60)
            logger.info("🚀 YASH WORLD - Firebase Firestore Version")
            logger.info("="*60)
            logger.info("📊 Database: Firebase Firestore (happybirthday-a287a)")
            logger.info("🔑 Admin (You): yash / admin123")
            logger.info("👤 Friend: Glory / lory")
            logger.info("💾 ALL DATA stored in Firebase - PERMANENT!")
            logger.info("="*60 + "\n")
            
        except Exception as e:
            logger.error(f"❌ Firebase initialization error: {e}")
    else:
        logger.warning("⚠️ Firebase not connected. Using local storage only.")

# Initialize database
init_db()

# ============================================================
# RUN THE APPLICATION
# ============================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)