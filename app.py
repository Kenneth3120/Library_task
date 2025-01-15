from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    name = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    borrows = db.relationship('Borrow', backref='user', lazy=True)
    books_added = db.relationship('Book', backref='added_by', lazy=True)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    isbn = db.Column(db.String(13), unique=True, nullable=False)
    available = db.Column(db.Boolean, default=True)
    added_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    added_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    borrows = db.relationship('Borrow', backref='book', lazy=True)

class Borrow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    borrow_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    return_date = db.Column(db.DateTime)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    search = request.args.get('search', '')
    if search:
        books = Book.query.filter(
            (Book.title.ilike(f'%{search}%')) | 
            (Book.author.ilike(f'%{search}%'))
        ).all()
    else:
        books = Book.query.all()
    return render_template('index.html', books=books, search=search)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid email or password')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(url_for('signup'))
            
        user = User(
            email=email,
            name=name,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('index'))
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/add-book', methods=['GET', 'POST'])
@login_required
def add_book():
    if request.method == 'POST':
        title = request.form.get('title')
        author = request.form.get('author')
        isbn = request.form.get('isbn')
        
        if Book.query.filter_by(isbn=isbn).first():
            flash('A book with this ISBN already exists')
            return redirect(url_for('add_book'))
            
        book = Book(
            title=title,
            author=author,
            isbn=isbn,
            added_by_id=current_user.id
        )
        db.session.add(book)
        db.session.commit()
        flash('Book added successfully')
        return redirect(url_for('index'))
        
    return render_template('add_book.html')

@app.route('/borrow/<int:book_id>')
@login_required
def borrow_book(book_id):
    book = Book.query.get_or_404(book_id)
    if not book.available:
        flash('Book is not available')
        return redirect(url_for('index'))
    
    borrow = Borrow(user_id=current_user.id, book_id=book_id)
    book.available = False
    db.session.add(borrow)
    db.session.commit()
    flash('Book borrowed successfully')
    return redirect(url_for('my_books'))

@app.route('/return/<int:book_id>')
@login_required
def return_book(book_id):
    borrow = Borrow.query.filter_by(
        user_id=current_user.id,
        book_id=book_id,
        return_date=None
    ).first_or_404()
    
    borrow.return_date = datetime.utcnow()
    borrow.book.available = True
    db.session.commit()
    flash('Book returned successfully')
    return redirect(url_for('my_books'))

@app.route('/my-books')
@login_required
def my_books():
    borrowed_books = Borrow.query.filter_by(
        user_id=current_user.id,
        return_date=None
    ).all()
    added_books = Book.query.filter_by(added_by_id=current_user.id).all()
    return render_template('my_books.html', borrows=borrowed_books, added_books=added_books)

@app.route('/manage-books')
@login_required
def manage_books():
    if not current_user.is_admin:
        flash('Only administrators can access this page')
        return redirect(url_for('index'))
    
    books = Book.query.all()
    borrows = Borrow.query.filter_by(return_date=None).all()
    return render_template('manage_books.html', books=books, borrows=borrows)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create admin user if it doesn't exist
        admin_email = "admin@library.com"
        if not User.query.filter_by(email=admin_email).first():
            admin = User(
                email=admin_email,
                name="Admin",
                password_hash=generate_password_hash("admin123"),
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True)