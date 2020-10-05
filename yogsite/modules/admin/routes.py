from datetime import datetime

from flask import abort
from flask import Blueprint
from flask import flash
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for

from flask_login import login_required
from flask_login import login_user
from flask_login import logout_user

from sqlalchemy import or_, and_

import math

from yogsite import db
from yogsite.config import cfg
from yogsite.util import is_safe_redirect

from .forms import SetLOAForm

blueprint = Blueprint("admin", __name__)

@blueprint.route("/login", methods=["GET", "POST"])
def page_login():
	if request.method == "POST":
		login_ckey = request.form.get("ckey")
		login_pass = request.form.get("password")

		admin_account = db.Admin.from_ckey(login_ckey)

		if admin_account and admin_account.check_password(login_pass):
			login_user(admin_account, remember=True)

			flash("Successfully Logged In", "success")

			redirect_url = request.args.get('next')

			if not is_safe_redirect(redirect_url):
				return abort(400)
			
			return redirect(redirect_url or "/")

		else:
			flash("Received Invalid Credentials", "error")

	return render_template("admin/login.html")


@blueprint.route("/logout")
def page_logout():
	logout_user()
	flash("Successfully Logged Out", "success")
	return redirect("/")


@blueprint.route("/admin/admins", methods=["GET", "POST"])
def page_manage_admins():

	form_set_loa = SetLOAForm(request.form, prefix="form_set_loa")

	admins = db.game_db.query(db.Admin).order_by(db.Admin.ckey) # Get admins sorted by ckey

	loas = db.game_db.query(db.LOA).filter(
		and_(
			or_(
				db.LOA.revoked == 0,
				db.LOA.revoked == None # don't ask me why it has to be done like this, I, don't know.
			),
			db.LOA.expiry_time > datetime.utcnow()
		)
	).order_by(db.LOA.time) # Get LOAs sorted by start time

	admin_ranks = db.game_db.query(db.AdminRank)

	if request.method == "POST":
		if form_set_loa.validate_on_submit():
			print ("loa works")
			return redirect(url_for("admin.page_manage_admins"))

	return render_template("admin/manage_admins.html", 
		admins=admins, loas=loas, admin_ranks=admin_ranks,
		form_set_loa = form_set_loa
	)


@blueprint.route("/admin/loa/<int:loa_id>/<string:action>")
def page_loa_action(loa_id, action):

	loa = db.LOA.from_id(loa_id)

	if action == "revoke":
		loa.set_revoked(True)
	
	return redirect(request.referrer)