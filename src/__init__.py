from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from os import path
from flask_login import LoginManager
from flask_mail import Mail
import stripe

db = SQLAlchemy()
DB_NAME = "database.db"

# this is the root of directory for all uploading images. note: don't modify this
UPLOAD_FOLDER = "src/static/img/"

# put your domain name exact this way... e.g: https://example.com
domain = ""

# put into "" double quotation, your stripe publishable and secret keys
pub_key = "pk_test_TYooMQauvdEDq54NiTphI7jx"
sec_key = "sk_test_4eC39HqLyjWDarjtT1zdp7dc"

"""
set your email config: mail_smtp is like: smtp.gmail.com, mail_user: is your email@gmail.com, mail_pass: is your orginal password of that email you've provided in user_mail & mail_port : is by default 587 for TLS
"""
mail_smtp = ""
mail_user = ""
mail_pass = ""
mail_port = 587
mail_subject = "" # put here subject for email
mail_response = "" # put here what messages you wanna show to user after a contact submission

"""
this message will show, when user submitted time/period isn't available.
hint: sorry, this room isn't availble for period! try another...
"""
chk_error_res = ""


stripe_keys = {
  'secret_key': sec_key,
  'publishable_key': pub_key
  }
stripe.api_key = stripe_keys['secret_key']

# all configurations
def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = "A?3r3}y!S(!6yx{Z6:L5$X>5Yn"
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAIL_SERVER'] = mail_smtp
    app.config['MAIL_USERNAME'] = mail_user
    app.config['MAIL_PASSWORD'] = mail_pass
    app.config['MAIL_PORT'] = mail_port
    app.config['MAIL_USE_TLS'] = True
    app.config['DEFAULT_MAIL_SENDER'] = mail_user

    
    db.init_app(app)
    migrate = Migrate(app, db)

    mail = Mail()
    mail.init_app(app)

    # making blueprint of these files
    from .views import views
    from .auth import auth

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')

    from .models import User

    create_database(app)

    # initializing flask_login manager
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))

    return app

# create database.db file if not exist in directory
def create_database(app):
    if not path.exists('src/' + DB_NAME):
        db.create_all(app=app)
        print('Database has been created successfully')