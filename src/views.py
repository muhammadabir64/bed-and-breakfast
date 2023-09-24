from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for
from flask_login import login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from .models import User, Rooms, Booking, DailyEarning, DashboardInfo
from . import db, UPLOAD_FOLDER, pub_key, sec_key, stripe_keys, mail_user, mail_subject, mail_response, chk_error_res
import stripe
import os
import shutil
from datetime import date, timedelta
import datetime


# load blueprint and mail for views.py
views = Blueprint("views", __name__)
mail = Mail()

# remake user default avatar if not exist
def default_avatar():
	if not os.path.exists("src/static/img/user_avatars/default_user_img.png"):
		shutil.copy("src/static/img/default_user_img.png", "src/static/img/user_avatars/default_user_img.png")

# calculate total days
def total_days(check_in, check_out):
    chk_in_y = int(check_in.split('-')[0])
    chk_in_m = int(check_in.split('-')[1])
    chk_in_d = int(check_in.split('-')[2])
    chk_out_y = int(check_out.split('-')[0])
    chk_out_m = int(check_out.split('-')[1])
    chk_out_d = int(check_out.split('-')[2])
    chk_in = date(chk_in_y, chk_in_m, chk_in_d)
    chk_out = date(chk_out_y, chk_out_m, chk_out_d)
    return (chk_out - chk_in).days

# get date list
def check_in_date(chk_in):
    chk_in_y = int(chk_in.split('-')[0])
    chk_in_m = int(chk_in.split('-')[1])
    chk_in_d = int(chk_in.split('-')[2])
    chk_in = date(chk_in_y, chk_in_m, chk_in_d)
    return chk_in
def check_out_date(chk_out):
    chk_out_y = int(chk_out.split('-')[0])
    chk_out_m = int(chk_out.split('-')[1])
    chk_out_d = int(chk_out.split('-')[2])
    chk_out = date(chk_out_y, chk_out_m, chk_out_d)
    return chk_out
def daterange(chkin, chkout):
    for n in range(int ((chkout - chkin).days)+1):
        yield chkin + timedelta(n)

# check expired dates of reserved rooms & free them if expire=true
def check_booking_expire():
    today_date = datetime.datetime.today().date()
    room_expired = Booking.query.filter_by(expire_date=today_date).first()
    if room_expired:
    	db.session.delete(room_expired)
    	db.session.commit()

# check exists of table rows
def check_row_exist():
	todayDate = datetime.datetime.today().date()
	daily_earning = DailyEarning.query.filter_by(id=1).first()
	total_earnings = DashboardInfo.query.filter_by(id=1).first()
	if not daily_earning:
		db.session.add(DailyEarning(id=1, today_date=todayDate, earning=0))
		db.session.commit()
	if not total_earnings:
		db.session.add(DashboardInfo(id=1, total_earning=0))
		db.session.commit()

# check exists of row & show daily earings on admin dashboard
def daily_earn():
	todayDate = datetime.datetime.today().date() + timedelta(days=1)
	today_earn = DailyEarning.query.filter_by(id=1).first()
	db_date = today_earn.today_date
	db_date = datetime.datetime.strptime(db_date, "%Y-%m-%d").date()
	if db_date != todayDate:
		DailyEarning.query.filter_by(id=1).update(dict(today_date=todayDate, earning=0))
		db.session.commit()


# route for home page
@views.route("/")
@views.route("/home", methods=["GET", "POST"])
def home():
	if request.method == "GET":
		rooms = Rooms.query.all()
		default_avatar()
		check_booking_expire()
		return render_template("home.html", user=current_user, rooms=rooms)
	# this handle footer contact form
	if request.method == "POST":
		full_name = request.form.get("full_name")
		email = request.form.get("email")
		subject = request.form.get("subject")
		msg = request.form.get("message")
		mail_template = Message(mail_subject, sender=mail_user, recipients=[email])
		mail_template.body = f"Name : {full_name}\nFrom : {email}\nSubject : {subject}\n\n{msg}"
		mail.send(mail_template)
		return jsonify(mail_response)

# this route for room page
@views.route("/rooms")
def rooms():
	# fetching all rooms data from database and send it to room page
	rooms = Rooms.query.all()
	default_avatar()
	check_booking_expire()
	return render_template("rooms.html", user=current_user, room=rooms)

# this route for room booking page
@views.route("/room_book", methods=["GET", "POST"])
def room_book():
	room_id = request.args.get("room_id")
	room_data = Rooms.query.filter_by(id=room_id).first()
	return render_template("room_book.html", user=current_user, room_data=room_data)

# this route for confirm room booking and payment
@views.route("/room_book_confirm", methods=["GET", "POST"])
@login_required
def room_book_confirm():
	check_booking_expire()
	# fetching user and room booking informations from room_book page
	room_id = request.args.get('room_id')
	user_id = request.args.get('user_id')
	check_in = request.args.get('check_in')
	check_out = request.args.get('check_out')
	totalDays = total_days(check_in, check_out)
# check if: user submitted priod is available of this room
	reserved_dates = Booking.query.filter_by(reserved_room=room_id).first()
	if reserved_dates:
		# stored period in database for this room
		db_date_list = ()
		for db_dt in daterange(check_in_date(reserved_dates.chk_in_full), check_out_date(reserved_dates.chk_out_full)):
		    db_date_list += (db_dt.strftime("%Y-%m-%d"),)
		#check_in: user submitted period
		user_in_date_list = ()
		for user_in_dt in daterange(check_in_date(check_in), check_out_date(check_out)):
		    user_in_date_list += (user_in_dt.strftime("%Y-%m-%d"),)
		#check_out: user submitted period
		user_out_date_list = ()
		for user_out_dt in daterange(check_in_date(check_in), check_out_date(check_out)):
		    user_out_date_list += (user_out_dt.strftime("%Y-%m-%d"),)
# if date/period is available then foward next otherwise rediect to back page
		if any(item in user_in_date_list for item in db_date_list) or any(item in user_out_date_list for item in db_date_list):
			flash(chk_error_res, category="error")
			return redirect(url_for("views.room_book", room_id=room_id))
			
	user_data = User.query.filter_by(id=user_id).first()
	room_data = Rooms.query.filter_by(id=room_id).first()
	return render_template("room_book_confirm.html", user=current_user, user_data=user_data, room_data=room_data, check_in=check_in, check_out=check_out, totalDays=totalDays, key=stripe_keys['publishable_key'])

# handle payment confirmation and query database
@views.route("/room_book_payment", methods=["POST"])
@login_required
def room_book_payment():
    userID = request.form.get("user_id")
    roomID = request.form.get("room_id")
    check_in = request.form.get("check_in")
    check_out = request.form.get("check_out")
    amount = request.form.get("price")+"00"
    earn = request.form.get("price")
    email = request.form.get("email")
    description = request.form.get("description")
    get_user_mail = User.query.filter_by(id=userID).first()
    room_data = Rooms.query.filter_by(id=roomID).first()
    chk_in_y = check_in.split("-")[0]
    chk_in_m = check_in.split("-")[1]
    chk_in_d = check_in.split("-")[2]
    chk_out_y = check_out.split("-")[0]
    chk_out_m = check_out.split("-")[1]
    chk_out_d = check_out.split("-")[2]
    totalDays = total_days(check_in, check_out)
    expireDate = datetime.datetime.strptime(check_out, "%Y-%m-%d").date() + timedelta(days=1)
    check_booking_expire()

    customer = stripe.Customer.create(
        email=email,
        source=request.form['stripeToken']
    )
    charge = stripe.Charge.create(
        customer=customer.id,
        amount=amount,
        currency='eur',
        description=description
    )
    add_new_book = Booking(check_in_y=chk_in_y, check_in_m=chk_in_m, check_in_d=chk_in_d, check_out_y=chk_out_y, check_out_m=chk_out_m, check_out_d=chk_out_d, chk_in_full=check_in, chk_out_full=check_out, total_days=totalDays, reserved_by=userID, reserved_by_user=get_user_mail.email, reserved_room=roomID, reserved_room_title=room_data.title, reserved_room_thumb=room_data.thumb, reserved_room_price=room_data.price, expire_date=expireDate)


    total_prev_earn = DashboardInfo.query.filter_by(id=1).first()
    total_new_earn = (total_prev_earn.total_earning + int(earn))
    DashboardInfo.query.filter_by(id=1).update(dict(total_earning=total_new_earn))

    daily_prev_earn = DailyEarning.query.filter_by(id=1).first()
    daily_new_earn = (daily_prev_earn.earning + int(earn))
    DailyEarning.query.filter_by(id=1).update(dict(earning=daily_new_earn))

    db.session.add(add_new_book)
    db.session.commit()
    flash(f"Thank you {current_user.fname}, for making purchase. Room has been reserved for {totalDays} days", category="success")
    return redirect(url_for("views.user_dashboard"))

# this route for contact page
@views.route("/contact", methods=["GET", "POST"])
def contact():
	if request.method == "GET":
		default_avatar()
		check_booking_expire()
		return render_template("contact.html", user=current_user)
	if request.method == "POST":
		fname = request.form.get("fname")
		lname = request.form.get("lname")
		email = request.form.get("email")
		subject = request.form.get("subject")
		msg = request.form.get("message")
		mail_template = Message(mail_subject, sender=mail_user, recipients=[email])
		mail_template.body = f"Name : {fname} {lname}\nFrom : {email}\nSubject : {subject}\n\n{msg}"
		mail.send(mail_template)
		return jsonify(mail_response)

# this route for user dashboard/profile page
@views.route("/user_dashboard")
@login_required
def user_dashboard():
	user_booking_info = Booking.query.filter_by(reserved_by=current_user.id).all()
	default_avatar()
	check_booking_expire()
	return render_template("user/user_dashboard.html", user=current_user, user_booking=user_booking_info)

# this route for update/modify user details
@views.route("/user_personal_info", methods=["GET", "POST"])
@login_required
def user_personal_info():
	fname = request.form.get("fname")
	lname = request.form.get("lname")
	email = request.form.get("email")
	phone = request.form.get("phone")
	birth = request.form.get("birth")
	country = request.form.get("country")
	gender = request.form.get("gender")
	city = request.form.get("city")
	zip_code = request.form.get("zip_code")
	address = request.form.get("address")
	user_id = request.form.get("user_id")
	modify_user = User.query.filter_by(id=user_id).update(dict(fname=fname, lname=lname, email=email, phone=phone, date_of_birth=birth, country=country, gender=gender, city=city, zip_code=zip_code, address=address))
	db.session.commit()
	default_avatar()
	check_booking_expire()
	return redirect(url_for('views.user_dashboard'))

# this route for changing user profile picture
@views.route("/user_avatar", methods=["POST"])
@login_required
def user_avatar():
	avatar_img = request.files["user_avatar_img"]
	upload_to = f"{UPLOAD_FOLDER}user_avatars/"
	path = os.path.join(upload_to, avatar_img.filename)
	avatar_img.save(path)
	os.remove(f"src/static/img/user_avatars/{current_user.avatar}")
	User.query.filter_by(id=current_user.id).update(dict(avatar=avatar_img.filename))
	db.session.commit()
	flash("Profile picture uploaded successfully", category="success")
	return redirect(url_for("views.user_dashboard"))

# this route for admin dashboard, only for admin can access this page
@views.route("/admin_dashboard")
@login_required
def admin_dashboard():
	default_avatar()
	check_row_exist()
	daily_earn()
	check_booking_expire()
	# role:0 = user & role:1 = admin
	if current_user.role == 1:
		admin_count = User.query.filter_by(role=1).count()
		users_count = User.query.filter_by(role=0).count()
		rooms_count = Rooms.query.count()
		booking_count = Booking.query.count()
		dailyEarn = DailyEarning.query.filter_by(id=1).first()
		dashboardInfo = DashboardInfo.query.filter_by(id=1).first()
		roomReservedList = Booking.query.all()
		return render_template("admin/admin_dashboard.html", user=current_user, rooms_count=rooms_count, booking_count=booking_count, admin_count=admin_count, users_count=users_count, daily_earn=dailyEarn, dashboard_info=dashboardInfo, room_reserved_list=roomReservedList)
	else:
		return redirect(url_for('views.user_dashboard'))

# this route for room management page for admin
@views.route("/admin_room", methods=["GET", "POST"])
@login_required
def admin_room():
	if current_user.role == 1:
		if request.method == "GET":
			check_booking_expire()
			room_info = Rooms.query.all()
			return render_template("admin/room_list.html", user=current_user, room_data=room_info)
	else:
		return redirect(url_for('views.user_dashboard'))
	# add new room
	if request.method == "POST":
		title = request.form.get("title")
		price = request.form.get("price")
		description = request.form.get("description")
		bed = request.form.get("bed")
		wifi = request.form.get("wifi")
		lunch = request.form.get("lunch")
		thumbnail = request.files["thumbnail"]
		upload_to = f"{UPLOAD_FOLDER}admin_rooms/"
		path = os.path.join(upload_to, thumbnail.filename)
		thumbnail.save(path)
		add_room = Rooms(title=title, description=description, thumb=thumbnail.filename, price=price, bed=bed, lunch=lunch, wifi=wifi)
		db.session.add(add_room)
		db.session.commit()
		return redirect(url_for('views.admin_room'))

# this route handle room deletion operations
@views.route("/room_delete", methods=["POST"])
@login_required
def room_delete():
	del_room_id = request.form.get("del_room_id")
	room_del_query = Rooms.query.filter_by(id=del_room_id).first()
	os.remove(f"src/static/img/admin_rooms/{room_del_query.thumb}")
	db.session.delete(room_del_query)
	db.session.commit()
	return redirect(url_for("views.admin_room"))

# this route for user management for admin
@views.route("/users_list", methods=["GET", "POST"])
@login_required
def users_list():
	if current_user.role == 1:
		# fetch all users from database send to user_list page to show
		if request.method == "GET":
			check_booking_expire()
			return render_template("admin/users_list.html", user=current_user, user_data=User.query.all())
	else:
		return redirect(url_for('views.user_dashboard'))
	# this handle add new user operation
	if request.method == "POST":
		fname = request.form.get("fname")
		lname = request.form.get("lname")
		phone = request.form.get("phone")
		birth = request.form.get("birth")
		country = request.form.get("country")
		gender = request.form.get("gender")
		city = request.form.get("city")
		zip_code = request.form.get("zip_code")
		address = request.form.get("address")
		email = request.form.get("email")
		password = generate_password_hash(request.form.get("password"), method="sha256")
		# check if email is already exist in database
		fetch_email = User.query.filter_by(email=email).first()
		if fetch_email:
			flash("Email already exists!", category="error")
			return redirect (url_for ('views.users_list'))
		avatar_img = request.files["avatar"]
		avatar = ""
		# is user haven't uploaded any avatar then by default set one 
		if avatar_img.filename == "":
			avatar = "default_user_img.png"
		else:
			upload_to = f"{UPLOAD_FOLDER}user_avatars/"
			path = os.path.join(upload_to, avatar_img.filename)
			avatar_img.save(path)
			avatar = avatar_img.filename
		new_user = User(fname=fname, lname=lname, phone=phone, date_of_birth=birth, country=country, gender=gender, city=city, zip_code=zip_code, address=address, email=email, password=password, avatar=avatar)
		db.session.add(new_user)
		db.session.commit()
		flash("New user has added successfully", category="success")
		return redirect(url_for("views.users_list"))

# this route handle user details update/modify operations 
@views.route("/user_modify", methods=["GET", "POST"])
@login_required
def user_modify():
	if current_user.role == 1:
		# fetch current details of user to show
		if request.method == "GET":
			user_id = request.args.get("user_id")
			fetch_user_data = User.query.filter_by(id=user_id).first()
			default_avatar()
			return render_template("admin/user_modify.html", user=current_user, user_data=fetch_user_data)
	else:
		return redirect(url_for('views.user_dashboard'))
	# update save changes data
	if request.method == "POST":
		fname = request.form.get("fname")
		lname = request.form.get("lname")
		phone = request.form.get("phone")
		birth = request.form.get("birth")
		country = request.form.get("country")
		gender = request.form.get("gender")
		city = request.form.get("city")
		zip_code = request.form.get("zip_code")
		address = request.form.get("address")
		email = request.form.get("email")
		role = request.form.get("role")
		modify_user_id = request.form.get("modify_user_id")
		# if new avatar isn't uploaded then set current avatar
		avatar_img = request.files["avatar"]
		avatar = ""
		old_avatar = User.query.filter_by(id=modify_user_id).first()
		if avatar_img.filename == "":
			avatar = old_avatar.avatar
		else:
			upload_to = f"{UPLOAD_FOLDER}user_avatars/"
			path = os.path.join(upload_to, avatar_img.filename)
			avatar_img.save(path)
			os.remove(f"src/static/img/user_avatars/{old_avatar.avatar}")
			avatar = avatar_img.filename

		User.query.filter_by(id=modify_user_id).update(dict(fname=fname, lname=lname, phone=phone, date_of_birth=birth, country=country, gender=gender, city=city, zip_code=zip_code, address=address, email=email, role=role, avatar=avatar))
		db.session.commit()
		flash("Save changes successfully", category="success")
		return redirect(url_for("views.user_modify", user_id=modify_user_id))

# this route handle user deletion operations also user avatar from directory for save spaces
@views.route("/user_delete", methods=["POST"])
@login_required
def user_delete():
	del_user_id = request.form.get("del_user_id")
	user_del_query = User.query.filter_by(id=del_user_id).first()
	if os.path.exists(f"{UPLOAD_FOLDER}user_avatars/{user_del_query.avatar}"):
		os.remove(f"{UPLOAD_FOLDER}user_avatars/{user_del_query.avatar}")
	else:
		pass
	db.session.delete(user_del_query)
	db.session.commit()
	flash("User has deleted", category="success")
	return redirect(url_for("views.users_list"))

# this route for handle changing user password from admin panel
@views.route("/change_user_pass", methods=["POST"])
@login_required
def change_user_pass():
	# fetching user submitted data
	pass_user_id = request.form.get("pass_user_id")
	old_pass = request.form.get("old_pass")
	new_pass = request.form.get("new_pass")
	# fetch old password from database
	fetch_old_pass = User.query.filter_by(id=pass_user_id).first()
	# if old password patch with new password then save changes
	if check_password_hash(fetch_old_pass.password, old_pass):
		gen_new_hash = generate_password_hash(new_pass, method="sha256")
		User.query.filter_by(id=pass_user_id).update(dict(password=gen_new_hash))
		db.session.commit()
		flash("Password has changed successfully", category="success")
		return redirect(url_for("views.user_modify", user_id=pass_user_id))
	else:
		flash("Old password doesn't match!", category="error")
		return redirect(url_for("views.user_modify", user_id=pass_user_id))