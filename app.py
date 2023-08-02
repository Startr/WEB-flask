from flask import Flask, flash, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, current_user

from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from functools import wraps

import csv
import os
import re
import stripe

from flask_cloudflared import run_with_cloudflared


config = {
    "DEBUG": True,  # run app in debug mode
    "SQLALCHEMY_DATABASE_URI": "sqlite:///db.sqlite"  # connect to database
}


stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

app = Flask(__name__, static_url_path='')

app.secret_key = os.getenv("FLASK_SECRET_KEY")

app.config.from_mapping(config)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/test.db'

db = SQLAlchemy(app)

# if app.config['DEBUG']:
#    run_with_cloudflared(app)

# Create uploads directory if it doesn't exist
if not os.path.exists('uploads'):
    os.makedirs('uploads')

login_manager = LoginManager()
login_manager.init_app(app)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    account_type = db.Column(db.String(100))


with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    __tablename__ = 'user'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    account_type = db.Column(db.String(100))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def check_message(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        message = request.args.get('message')
        return f(*args, **kwargs)
    return decorated_function


def swuped(content, link="/dashboard", message="Go to the dash"):
    """
    Wrap html in swup div to allow for simple page transitions of content.
    content -- html to display
    link -- link to another page
    message -- anchor text for link
    """
    return f"""
    <main id="swup" class="transition-fade">
        <h1>{content}</h1>
        <a href="{link}">{message}</a>
    </main>
    """


@app.route('/', methods=['GET', 'POST'])
@check_message
def index():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        cv = request.files.get('cv')  # Changed to use get method

        # Check if name and email are provided
        if not name or not email:
            return redirect(url_for('index', message="Please provide both your name and email."))

        with open('contacts.csv', 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([name, email])

        if cv:
            filename = secure_filename(cv.filename)
            email_filename = re.sub(r'@', '_at_', email)
            cv_filename = f"{email_filename}.pdf"
            cv.save(os.path.join('uploads', cv_filename))

        return redirect(url_for('index', message="Thank you for submitting!"))

    return render_template('index.html', message=request.args.get('message'))


@app.route('/about')
def about():
    return swuped('This is the about page.', link="/contact", message="Go to the contact page.")


@app.route('/contact')
def contact():
    return swuped('This is the contact page.')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get email and password from form
        email = request.form.get('email')
        password = request.form.get('password')

        # Find user by email
        user = User.query.filter_by(email=email).first()

        # Check password
        if not user or not check_password_hash(user.password, password):
            return redirect(url_for('login', message="Incorrect email or password."))

        # Login user
        login_user(user)

        # Redirect to dashboard
        return redirect(url_for('dashboard', message="You have been logged in."))
    # Get message from query string
    message = request.args.get('message')
    return render_template('login.html', message=message)

# Logout route


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login', message="You have been logged out."))


@app.route('/register', methods=['GET', 'POST'])
@check_message
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        password = generate_password_hash(
            request.form.get('password'), method='sha256')
        new_user = User(email=email, name=name,
                        password=password, account_type='free')
        # Handle existing user collision
        if User.query.filter_by(email=email).first():
            return redirect(url_for('register', message="Email address already exists."))
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('dashboard'))
    message = request.args.get('message')

    return render_template('register.html', message=message)


# Redirect @login_required when not logged in to login page
@login_manager.unauthorized_handler
def unauthorized_callback():
    return redirect(url_for('login', message='You must be logged in to view that page.'))


@app.route('/dashboard')
@check_message
@login_required
def dashboard():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append(str(rule))
    return render_template('dashboard.html', routes=routes)


@app.route('/upgrade', methods=['GET', 'POST'])
@login_required
def upgrade():
    if request.method == 'POST':
        payment_intent_id = request.form['payment_intent_id']
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        if payment_intent.status == 'succeeded':
            current_user.account_type = 'pro'
            db.session.commit()
            return swuped('You are now a pro user.', link="/pro_page", message="Go to the pro page.")

    else:
        # create a new PaymentIntent for the upgrade fee
        payment_intent = stripe.PaymentIntent.create(
            amount=5000,  # $50, amount is in cents
            currency='usd',
        )
    return render_template('upgrade.html', client_secret=payment_intent.client_secret, stripe_publishable_key=os.getenv("STRIPE_PUBLISHABLE_KEY"))


@app.route('/free_page')
@check_message
@login_required
def free_page():
    # return '   <main id="swup" class="transition-fade">This is the free page. <a href="/">Go back.</a></main>'
    return swuped('This is the free page.', link="/pro_page", message="Go Pro for more!")


@app.route('/pro_page')
@check_message
@login_required
def pro_page():
    if current_user.account_type == 'pro':
        return swuped('This is the pro page. ' + str(current_user) , link="/dashboard", message="Go to the dash")

    else:
        return redirect(url_for('upgrade'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
