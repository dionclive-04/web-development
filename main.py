from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from functools import wraps
import forms
from forms import CreatePostForm, Registerform, Commentform
from flask_gravatar import Gravatar

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap(app)

## CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

# parent
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), nullable=False, unique=True)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")

## CONFIGURE TABLES
# *child
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="parent_post")

# child
class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    text = db.Column(db.Text, nullable=False)
    comment_author = relationship("User", back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")

gravators = Gravatar(
    size=100,
    rating='g',
    default='retro',
)
with app.app_context():
    db.create_all()

@app.route('/')
def get_all_posts():
    admin_access = False
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, current_user=current_user, admin_access=admin_access)

@app.route('/register', methods=["GET", "POST"])
def register():
    error = None
    form = Registerform()
    if request.method == "POST":
        db_email = User.query.filter_by(email=form.email.data).first()
        if db_email:
            error = "This email is already registered"
            return render_template('login.html', form=forms.LoginForm(), error=error, current_user=current_user)

        user = User(email=form.email.data,
                    password=generate_password_hash(form.password.data, method='pbkdf2:sha256', salt_length=8),
                    name=form.name.data)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("get_all_posts"))

    return render_template("register.html", form=form, current_user=current_user)

@app.route('/login', methods=["GET", 'POST'])
def login():
    error = None
    form = forms.LoginForm()
    admin_access = False
    if request.method == "POST":
        email = form.email.data
        password = form.password.data
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.id == 1:
                posts = BlogPost.query.all()
                admin_access = True
                return render_template("index.html", admin_access=admin_access, current_user=current_user)
        if not user:
            error = "This email does not exist, please try again with a new one 🥲"
        else:
            error = "Invalid password, try with a different one 😊"
    return render_template('login.html', form=form, error=error, current_user=current_user)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))

@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    comments = Comment.query.all()
    form = Commentform()
    login_form = forms.LoginForm()
    error = None
    requested_post = BlogPost.query.get(post_id)
    if request.method == "POST":
        print(current_user.is_authenticated)
        if not current_user.is_authenticated:
            print("User is not authenticated")
            error = "You need to login or register to comment!"
            return render_template("login.html", form=login_form, error=error, current_user=current_user)
        else:
            print("User is authenticated")
            new_comment = Comment(text=form.comment_text.data, comment_author=current_user, parent_post=requested_post)
            db.session.add(new_comment)
            db.session.commit()
    return render_template("post.html", post=requested_post, current_user=current_user, form=form, comments=comments)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function

@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, current_user=current_user)

@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, current_user=current_user)

@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))

if __name__ == "__main__":
    app.run(debug=True)
