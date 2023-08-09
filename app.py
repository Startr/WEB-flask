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
    note -- optional note to display coming from query string
    """
    note = request.args.get('message')

    return f"""
<html>
  <head>
    <title>{content}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="/css/startr.css">
    <link rel="stylesheet" href="/css/style.css">
  </head>
  <body>
    <main id="swup" class="transition-fade">
        <h2>{content}</h2>
        {'<h3>' + note + '</h3>' if note else ''}
        <a href="{link}">{message}</a>
    </main>
  </body>
</html>
    """


@app.route('/')
@check_message
def index():
    return render_template('index.html', message=request.args.get('message'))


@app.route('/about')
def about():
    return swuped('This is the about page.', link="/contact", message="Go to the contact page.")


@app.route('/contact')
def contact():
    return swuped('This is the contact page.')


@app.route('/login', methods=['GET', 'POST'])
@check_message
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password, password):
            return redirect(url_for('login', message="Incorrect email or password."))

        login_user(user)

        return redirect(url_for('free_page', message="You have been logged in."))
    # Get message from query string
    message = request.args.get('message')
    return render_template('login.html', message=message)


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
        return redirect(url_for('free_page', message="You're now registered and logged in!"))
    message = request.args.get('message')

    return render_template('register.html', message=message)


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
    # If user is already a pro user, redirect to pro page
    if current_user.account_type == 'pro':
        return redirect(url_for('pro_page', message="You are already a pro user."))
    if request.args.get('payment_intent'):
        payment_intent_id = request.args.get('payment_intent')
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        if payment_intent.status == 'succeeded':
            current_user.account_type = 'pro'
            db.session.commit()
            return swuped('You are now a pro user.', link="/pro_page", message="Go to the pro page.")

    else:
        # Ask stripe for customer id based on email
        stripe_customer_list = stripe.Customer.list(email=current_user.email)
        # If customer exists, get the id
        if stripe_customer_list['data']:
            stripe_customer_id = stripe_customer_list['data'][0]['id']
        else:
            new_customer = stripe.Customer.create(email=current_user.email)
            stripe_customer_id = new_customer['id']

        # create a new PaymentIntent for the upgrade fee
        payment_intent = stripe.PaymentIntent.create(
            amount=int(float(os.getenv("PRO_PRICE")) * 100),  # price from .env
            customer=stripe_customer_id,
            receipt_email=current_user.email,
            currency='usd',
            automatic_payment_methods={
                'enabled': True,
            }
        )
    return render_template('upgrade.html', client_secret=payment_intent.client_secret, stripe_publishable_key=os.getenv("STRIPE_PUBLISHABLE_KEY"))


@app.route('/free_page', methods=['GET', 'POST'])
@check_message
@login_required
def free_page():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        job_description = request.form.get('job_description')
        cv = request.files.get('cv')  # Changed to use get method

        if not name or not email:  # Check if name and email are provided
            return redirect(url_for('index', message="Please provide both your name and email."))

        with open('contacts.csv', 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([name, email, job_description])

        if cv:
            filename = secure_filename(cv.filename)
            email_filename = re.sub(r'@', '_at_', email)
            cv_sufix = filename.split('.')[-1]
            cv_filename = f"{email_filename}.{cv_sufix}"
            cv.save(os.path.join('uploads', cv_filename))

        return swuped('Your application has been submitted.', link="/?submit_new_CV.", message="Submit another application.")

    return render_template('free_page.html', message=request.args.get('message'))


@app.route('/pro_page')
@check_message
@login_required
def pro_page():
    if current_user.account_type == 'pro':
        return swuped('This is the pro page. ' + str(current_user), link="/dashboard", message="Go to the dash")

    else:
        return redirect(url_for('upgrade'))


if __name__ == '__main__':
    app.jinja_env.auto_reload = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host='0.0.0.0', port=8000)
