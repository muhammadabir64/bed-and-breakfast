from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from .models import User
from werkzeug.security import generate_password_hash, check_password_hash
from . import db, mail_user, domain
from flask_login import login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
import os
import random
import string

# load blueprint and mail for auth.py
auth = Blueprint('auth', __name__)
mail = Mail()

# this route handle user/admin login
@auth.route('/login', methods=['GET', 'POST'])
def login():
    # fetch user submitted data
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        # check if user is exist or not
        user = User.query.filter_by(email=email).first()
        if user:
    # if user is exist then check password is match or not
            if check_password_hash(user.password, password):
    # if user password is match then set user login session
                login_user(user, remember=True)
    # if all above things is true then check is this user is 1:admin or 0:user
                if user.role == 0:
                    return redirect(url_for('views.home'))
                elif user.role == 1:
                    return redirect(url_for('views.admin_dashboard'))
            else:
                flash('Incorrect password, try again.', category='error')
        else:
            flash('Email does not exist.', category='error')

    return render_template("login.html", user=current_user)

# this route will logout user & admin also destroy login session
@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

# this route for sign up new user
@auth.route('/sign_up', methods=['GET', 'POST'])
def sign_up():
    # fetching user submitted data
    if request.method == 'POST':
        email = request.form.get('email')
        first_name = request.form.get('fname')
        last_name = request.form.get('lname')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')
        # check if email is already exist or not
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists.', category='error')
        # check if email length. it shoulb be at least 13 characters
        elif len(email) < 13:
            flash('Email must be greater than 3 characters.', category='error')
        # check length of first name
        elif len(first_name) < 2:
            flash('First name must be greater than 1 character.', category='error')
        # check length of last name
        elif len(last_name) < 2:
            flash('Last name must be greater than 1 character.', category='error')
        # check if password & confirm password is match or not
        elif password1 != password2:
            flash('Passwords don\'t match.', category='error')
        # check if password length is at least grater than 8 characters
        elif len(password1) < 7:
            flash('Password must be at least 7 characters.', category='error')
        # if everything is true all above, then add new user into database and redirect to login page
        else:
            new_user = User(email=email, fname=first_name, lname=last_name, password=generate_password_hash(
                password1, method='sha256'))
            db.session.add(new_user)
            db.session.commit()
            flash('Account has been created successfully. Please login to continue...', category='success')
            return redirect(url_for('auth.login'))

    return render_template("sign_up.html", user=current_user)

# this route for forgot password page
@auth.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if request.method == "GET":
        return render_template("forgot_pass.html", user=current_user)
    # fetch user submitted data
    if request.method == "POST":
        email = request.form.get("email")
        # check: is this user exist in database
        fetch_user = User.query.filter_by(email=email).first()
        if fetch_user:
            """ if user is exist then generate a random string for create reset password url and save it into database """
            hashCode = ''.join(random.choices(string.ascii_letters + string.digits, k=75))
            fetch_user.hashCode = hashCode
            db.session.commit()
            """ after complete all above then send a password reset email to user provided email address """
            msg = Message('Your password reset link', sender=mail_user, recipients=[email])
            msg.body = f"Hello {fetch_user.fname},\nWe've received a request to reset your password. Click the link bellow and set a new password.\nlink: {domain}/password_reset_confirmation_url/{fetch_user.hashCode}"
            mail.send(msg)
            flash("We've sent a password reset link to your email", category="success")
            return redirect(url_for("auth.reset_password"))
        else:
            flash("User not exists!", category="error")
            return redirect(url_for("auth.reset_password"))

# this route handle: when user click password reset url from sent email
@auth.route("/password_reset_confirmation_url/<string:hashCode>")
def password_reset_confirmation_url(hashCode):
    # fetch hash code from database that was created before
    fetch_hash = User.query.filter_by(hashCode=hashCode).first()
    if fetch_hash:
        # if hash code is matched then show/render add new password form
        return render_template("set_new_pass.html", user_id=fetch_hash.id, user=current_user)
    else:
        flash("Password reset link has been expired", category="error")
        return redirect(url_for("auth.login"))

# this handler route save new password
@auth.route("/set_new_pass", methods=["GET", "POST"])
def set_new_pass():
    if request.method == "POST":
        password = request.form.get("password")
        user_id = request.form.get("user_id")
        User.query.filter_by(id=user_id).update(dict(password=generate_password_hash(password, method="sha256"), hashCode=0))
        db.session.commit()
        # if password has changed then redirect to login page
        flash("Your password has been changed successfully", category="success")
        return redirect(url_for('auth.login'))

# this route for handle changing user password from user profile page
@auth.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    # render/show change password form page
    if request.method == "GET":
        return render_template("user/change_password.html", user=current_user)
    # fetch user submitted data
    if request.method == "POST":
        old_pass = request.form.get("old_pass")
        new_pass = request.form.get("new_pass")
        re_pass = request.form.get("re_pass")
    # check: if new password & confirm password is match or not
        if new_pass == re_pass:
            # check: if old password is match with user submitted old_pass
            if check_password_hash(current_user.password, old_pass):
                gen_hash_pass = generate_password_hash(new_pass, method="sha256")
                User.query.filter_by(id=current_user.id).update(dict(password=gen_hash_pass))
            # if all above is true then put new password into database & save changes
                db.session.commit()
                flash("Your password has been changed successfully", category='success')
                return redirect(url_for('auth.change_password'))
            # redirect if old password doesn't match with database
            else:
                flash("Old password doesn't match!", category='error')
                return redirect(url_for('auth.change_password'))
        # redirect if old password doesn't match with new password
        else:
            flash("Couldn't match New password and Confirm password!", category='error')
            return redirect(url_for('auth.change_password'))

# this route handle user account deletion from user profile page
@auth.route("/user_account_delete", methods=["POST"])
@login_required
def user_account_delete():
    password = request.form.get("password")
    if check_password_hash(current_user.password, password):
        fetch_user = User.query.filter_by(id=current_user.id).first()
        os.remove(f"src/static/img/user_avatars/{fetch_user.avatar}")
        db.session.delete(fetch_user)
        db.session.commit()
        flash("Account has been deleted permanently", category="success")
        return redirect(url_for('auth.login'))
    else:
        flash("Invalid password! please try again...", category="error")
        return redirect(url_for('views.user_dashboard'))