from flask import abort, Blueprint, g, jsonify, render_template, request, Response, send_file

import math

from sqlalchemy import or_

from yogsite.config import cfg
from yogsite import db
from yogsite.util import login_required, perms_required

from .log_parsing import RoundLogs

blueprint = Blueprint("rounds", __name__)

@blueprint.route("/rounds")
def page_rounds():
	page = request.args.get('page', type=int, default=1)

	search_query = request.args.get('query', type=str, default=None)

	# This way of just shamelessly stringing together queries is probably bad and could be improved

	rounds_query = db.game_db.query(db.Round)

	if not g.current_user.has_perms("round.active"):
		rounds_query = rounds_query.filter(db.Round.shutdown_datetime.isnot(None))

	if search_query:
		# Search for rounds by either matching round id, game mode, or map name
		rounds_query = rounds_query.filter(
			or_(
				db.Round.id.like(search_query),
				db.Round.game_mode.like(search_query),
				db.Round.map_name.like(search_query)
			)
		)
	
	rounds_query = rounds_query.order_by(db.Round.id.desc())

	page_count = math.ceil(rounds_query.count() / cfg.get("items_per_page")) # Selecting only the id on a count is faster than selecting the entire row

	displayed_rounds = rounds_query.limit(cfg.get("items_per_page")).offset((page - 1) * cfg.get("items_per_page"))

	return render_template("rounds/rounds.html", rounds=displayed_rounds, page=page, page_count=page_count, search_query=search_query)


@blueprint.route("/rounds/<int:round_id>/logs")
@login_required
@perms_required("round.logs")
def page_round_logs(round_id):
	round = db.Round.from_id(round_id)

	if not round:
		return abort(404)

	return render_template("rounds/log_viewer/log_viewer.html", round=round)


@blueprint.route("/rounds/<int:round_id>/replay")
def page_round_replay(round_id):
	round = db.Round.from_id(round_id)

	if not round:
		return abort(404)

	in_progress = round.in_progress()

	if in_progress:
		if not g.current_user.has_perms("round.logs"):
			return abort(401) # The round is ongoing and the user doesn't have access to live round logs, unauthorized
	
	logs = RoundLogs(round_id)

	demo_file = logs.find_demo_file()

	if not demo_file: # There is no replay for this one
		abort(404)

	response = send_file(demo_file, conditional=True)

	# Header hell
	origin = request.environ.get("HTTP_ORIGIN")

	response.headers.add("Access-Control-Expose-Headers", "X-Allow-SS13-Replay-Streaming")
	response.headers.add("Access-Control-Allow-Origin", origin if origin else "*")

	if demo_file.endswith(".gz"):
		response.headers.add("Content-Encoding", "gzip")
	else:
		response.headers.add("X-Allow-SS13-Replay-Streaming", "true")
	
	if demo_file.endswith(".gz") or not round.in_progress():
		response.headers.add("Cache-Control", f"public,max-age={cfg.get('replay_viewer.max_cache_age')},immutable")

	if origin == cfg.get("replay_viewer.origin"):
		response.headers.add("Access-Control-Allow-Credentials", "true")
	
	return response


@blueprint.route("/api/rounds/<int:round_id>/logs")
@perms_required("round.logs")
def page_round_logs_api(round_id):
	logs = RoundLogs(round_id)
	entries = logs.load_entries()

	db.ActionLog.add(g.current_user.ckey, g.current_user.ckey, f"Looked at logs for round {round_id}")

	return jsonify([entry.to_dict() for entry in entries])