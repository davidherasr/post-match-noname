-- No Name PostMatch 3.7.0 · Esquema PostgreSQL de referencia
-- Generado desde SQLAlchemy. Alembic sigue siendo la fuente de verdad para migraciones.


CREATE TABLE app_settings (
	id SERIAL NOT NULL, 
	key VARCHAR(100) NOT NULL, 
	value TEXT, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (key)
);



CREATE TABLE competitions (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	country VARCHAR(80), 
	active BOOLEAN NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_competition_country UNIQUE (name, country)
);



CREATE TABLE players (
	id SERIAL NOT NULL, 
	full_name VARCHAR(180) NOT NULL, 
	normalized_name VARCHAR(180) NOT NULL, 
	display_name VARCHAR(100), 
	date_of_birth DATE, 
	nationality VARCHAR(80), 
	preferred_foot VARCHAR(20), 
	primary_position VARCHAR(20), 
	aliases TEXT, 
	photo_b64 TEXT, 
	photo_mime VARCHAR(80), 
	active BOOLEAN NOT NULL, 
	merged_into_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_player_identity UNIQUE (normalized_name, date_of_birth), 
	FOREIGN KEY(merged_into_id) REFERENCES players (id) ON DELETE SET NULL
);

CREATE INDEX ix_players_full_name ON players (full_name);
CREATE INDEX ix_players_normalized_name ON players (normalized_name);


CREATE TABLE seasons (
	id SERIAL NOT NULL, 
	name VARCHAR(40) NOT NULL, 
	start_date DATE, 
	end_date DATE, 
	active BOOLEAN NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);



CREATE TABLE teams (
	id SERIAL NOT NULL, 
	name VARCHAR(140) NOT NULL, 
	short_name VARCHAR(40), 
	country VARCHAR(80), 
	logo_b64 TEXT, 
	logo_mime VARCHAR(80), 
	is_own_team BOOLEAN NOT NULL, 
	active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_teams_name ON teams (name);


CREATE TABLE users (
	id SERIAL NOT NULL, 
	full_name VARCHAR(120) NOT NULL, 
	email VARCHAR(180) NOT NULL, 
	password_hash TEXT NOT NULL, 
	role VARCHAR(30) NOT NULL, 
	active BOOLEAN NOT NULL, 
	must_change_password BOOLEAN NOT NULL, 
	failed_login_count INTEGER NOT NULL, 
	locked_until TIMESTAMP WITHOUT TIME ZONE, 
	session_revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	last_login_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);


CREATE TABLE audit_logs (
	id SERIAL NOT NULL, 
	user_id INTEGER, 
	action VARCHAR(100) NOT NULL, 
	entity_type VARCHAR(80), 
	entity_id INTEGER, 
	detail TEXT, 
	before_json TEXT, 
	after_json TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);



CREATE TABLE game_model_roles (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	position VARCHAR(20) NOT NULL, 
	description TEXT, 
	active BOOLEAN NOT NULL, 
	order_index INTEGER NOT NULL, 
	created_by INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_game_model_role UNIQUE (name, position), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);



CREATE TABLE league_player_profiles (
	id SERIAL NOT NULL, 
	player_id INTEGER NOT NULL, 
	decision_status VARCHAR(40) NOT NULL, 
	priority INTEGER NOT NULL, 
	director_note TEXT, 
	updated_by INTEGER NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_league_player_profile UNIQUE (player_id), 
	FOREIGN KEY(player_id) REFERENCES players (id) ON DELETE CASCADE, 
	FOREIGN KEY(updated_by) REFERENCES users (id)
);



CREATE TABLE login_attempts (
	id SERIAL NOT NULL, 
	email VARCHAR(180) NOT NULL, 
	user_id INTEGER, 
	success BOOLEAN NOT NULL, 
	detail TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_login_attempts_email ON login_attempts (email);


CREATE TABLE matches (
	id SERIAL NOT NULL, 
	season_id INTEGER NOT NULL, 
	competition_id INTEGER NOT NULL, 
	round_name VARCHAR(80) NOT NULL, 
	match_date DATE NOT NULL, 
	window_start DATE, 
	window_end DATE, 
	kickoff_at TIMESTAMP WITHOUT TIME ZONE, 
	schedule_status VARCHAR(30) NOT NULL, 
	fixture_type VARCHAR(30) NOT NULL, 
	home_team_id INTEGER NOT NULL, 
	away_team_id INTEGER NOT NULL, 
	home_score INTEGER, 
	away_score INTEGER, 
	venue VARCHAR(160), 
	home_formation VARCHAR(40), 
	away_formation VARCHAR(40), 
	status VARCHAR(30) NOT NULL, 
	report_due_at TIMESTAMP WITHOUT TIME ZONE, 
	revision INTEGER NOT NULL, 
	deleted_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_match_different_teams CHECK (home_team_id <> away_team_id), 
	FOREIGN KEY(season_id) REFERENCES seasons (id), 
	FOREIGN KEY(competition_id) REFERENCES competitions (id), 
	FOREIGN KEY(home_team_id) REFERENCES teams (id), 
	FOREIGN KEY(away_team_id) REFERENCES teams (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);



CREATE TABLE player_aliases (
	id SERIAL NOT NULL, 
	player_id INTEGER NOT NULL, 
	alias VARCHAR(180) NOT NULL, 
	normalized_alias VARCHAR(180) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_player_alias UNIQUE (normalized_alias), 
	FOREIGN KEY(player_id) REFERENCES players (id) ON DELETE CASCADE
);

CREATE INDEX ix_player_aliases_normalized_alias ON player_aliases (normalized_alias);


CREATE TABLE player_merge_logs (
	id SERIAL NOT NULL, 
	source_player_id INTEGER NOT NULL, 
	target_player_id INTEGER NOT NULL, 
	actor_id INTEGER NOT NULL, 
	detail TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(target_player_id) REFERENCES players (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
);



CREATE TABLE postmatch_drafts (
	id SERIAL NOT NULL, 
	created_by INTEGER NOT NULL, 
	season_id INTEGER, 
	title VARCHAR(180), 
	payload_json TEXT NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(season_id) REFERENCES seasons (id) ON DELETE SET NULL
);



CREATE TABLE scouted_player_profiles (
	id SERIAL NOT NULL, 
	player_id INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	model_position VARCHAR(20), 
	model_role VARCHAR(80), 
	fit_score FLOAT, 
	current_level FLOAT, 
	potential_score FLOAT, 
	final_decision VARCHAR(50), 
	director_summary TEXT, 
	requested_by INTEGER NOT NULL, 
	assigned_to INTEGER, 
	approved_by INTEGER, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	approved_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_scouted_player_profile UNIQUE (player_id), 
	FOREIGN KEY(player_id) REFERENCES players (id) ON DELETE CASCADE, 
	FOREIGN KEY(requested_by) REFERENCES users (id), 
	FOREIGN KEY(assigned_to) REFERENCES users (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id)
);



CREATE TABLE scouting_lists (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	description TEXT, 
	list_type VARCHAR(30) NOT NULL, 
	formation VARCHAR(40), 
	season_id INTEGER, 
	active BOOLEAN NOT NULL, 
	created_by INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(season_id) REFERENCES seasons (id) ON DELETE SET NULL, 
	FOREIGN KEY(created_by) REFERENCES users (id)
);



CREATE TABLE team_rosters (
	id SERIAL NOT NULL, 
	team_id INTEGER NOT NULL, 
	season_id INTEGER NOT NULL, 
	player_id INTEGER NOT NULL, 
	shirt_number INTEGER, 
	active BOOLEAN NOT NULL, 
	joined_at DATE, 
	left_at DATE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_roster_player UNIQUE (team_id, season_id, player_id), 
	FOREIGN KEY(team_id) REFERENCES teams (id) ON DELETE CASCADE, 
	FOREIGN KEY(season_id) REFERENCES seasons (id) ON DELETE CASCADE, 
	FOREIGN KEY(player_id) REFERENCES players (id) ON DELETE CASCADE
);



CREATE TABLE user_roles (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	role VARCHAR(30) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_user_role UNIQUE (user_id, role), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);



CREATE TABLE consolidated_reports (
	id SERIAL NOT NULL, 
	match_id INTEGER NOT NULL, 
	rival_team_id INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	overview TEXT, 
	key_takeaways TEXT, 
	created_by INTEGER NOT NULL, 
	approved_by INTEGER, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	approved_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_consolidated_match_rival UNIQUE (match_id, rival_team_id), 
	FOREIGN KEY(match_id) REFERENCES matches (id) ON DELETE CASCADE, 
	FOREIGN KEY(rival_team_id) REFERENCES teams (id), 
	FOREIGN KEY(created_by) REFERENCES users (id), 
	FOREIGN KEY(approved_by) REFERENCES users (id)
);



CREATE TABLE follow_ups (
	id SERIAL NOT NULL, 
	player_id INTEGER NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	priority INTEGER NOT NULL, 
	note TEXT, 
	assigned_to INTEGER, 
	next_review_date DATE, 
	target_match_id INTEGER, 
	closed_reason TEXT, 
	revision INTEGER NOT NULL, 
	created_by INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_followup_player UNIQUE (player_id), 
	FOREIGN KEY(player_id) REFERENCES players (id) ON DELETE CASCADE, 
	FOREIGN KEY(assigned_to) REFERENCES users (id), 
	FOREIGN KEY(target_match_id) REFERENCES matches (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);



CREATE TABLE game_model_criteria (
	id SERIAL NOT NULL, 
	role_id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	category VARCHAR(30) NOT NULL, 
	description TEXT, 
	weight INTEGER NOT NULL, 
	order_index INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_model_role_criterion UNIQUE (role_id, name), 
	FOREIGN KEY(role_id) REFERENCES game_model_roles (id) ON DELETE CASCADE
);



CREATE TABLE participations (
	id SERIAL NOT NULL, 
	match_id INTEGER NOT NULL, 
	team_id INTEGER NOT NULL, 
	player_id INTEGER NOT NULL, 
	shirt_number INTEGER, 
	starter BOOLEAN NOT NULL, 
	position VARCHAR(20), 
	minute_in INTEGER NOT NULL, 
	minute_out INTEGER NOT NULL, 
	captain BOOLEAN NOT NULL, 
	order_index INTEGER NOT NULL, 
	revision INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_match_player UNIQUE (match_id, player_id), 
	CONSTRAINT ck_minute_in CHECK (minute_in >= 0), 
	CONSTRAINT ck_minute_order CHECK (minute_out >= minute_in), 
	FOREIGN KEY(match_id) REFERENCES matches (id) ON DELETE CASCADE, 
	FOREIGN KEY(team_id) REFERENCES teams (id), 
	FOREIGN KEY(player_id) REFERENCES players (id)
);



CREATE TABLE player_season_decisions (
	id SERIAL NOT NULL, 
	season_id INTEGER NOT NULL, 
	player_id INTEGER NOT NULL, 
	model_role_id INTEGER, 
	status VARCHAR(40) NOT NULL, 
	priority INTEGER NOT NULL, 
	director_note TEXT, 
	fit_score FLOAT, 
	current_level FLOAT, 
	potential_score FLOAT, 
	criteria_json TEXT, 
	updated_by INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_player_season_decision UNIQUE (season_id, player_id), 
	FOREIGN KEY(season_id) REFERENCES seasons (id) ON DELETE CASCADE, 
	FOREIGN KEY(player_id) REFERENCES players (id) ON DELETE CASCADE, 
	FOREIGN KEY(model_role_id) REFERENCES game_model_roles (id) ON DELETE SET NULL, 
	FOREIGN KEY(updated_by) REFERENCES users (id)
);



CREATE TABLE report_assignments (
	id SERIAL NOT NULL, 
	match_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	assigned_by INTEGER NOT NULL, 
	required BOOLEAN NOT NULL, 
	due_at TIMESTAMP WITHOUT TIME ZONE, 
	status VARCHAR(30) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_match_assignment_user UNIQUE (match_id, user_id), 
	FOREIGN KEY(match_id) REFERENCES matches (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(assigned_by) REFERENCES users (id)
);



CREATE TABLE reports (
	id SERIAL NOT NULL, 
	match_id INTEGER NOT NULL, 
	reporter_id INTEGER NOT NULL, 
	own_team_id INTEGER NOT NULL, 
	rival_team_id INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	rival_level VARCHAR(40), 
	opponent_overview TEXT, 
	own_team_note TEXT, 
	key_takeaways TEXT, 
	standout_player_id INTEGER, 
	version INTEGER NOT NULL, 
	revision INTEGER NOT NULL, 
	reviewer_id INTEGER, 
	review_note TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	submitted_at TIMESTAMP WITHOUT TIME ZONE, 
	approved_at TIMESTAMP WITHOUT TIME ZONE, 
	finalized_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_match_reporter UNIQUE (match_id, reporter_id), 
	FOREIGN KEY(match_id) REFERENCES matches (id) ON DELETE CASCADE, 
	FOREIGN KEY(reporter_id) REFERENCES users (id), 
	FOREIGN KEY(own_team_id) REFERENCES teams (id), 
	FOREIGN KEY(rival_team_id) REFERENCES teams (id), 
	FOREIGN KEY(standout_player_id) REFERENCES players (id), 
	FOREIGN KEY(reviewer_id) REFERENCES users (id)
);



CREATE TABLE scout_missions (
	id SERIAL NOT NULL, 
	match_id INTEGER NOT NULL, 
	mission_type VARCHAR(40) NOT NULL, 
	target_team_id INTEGER, 
	title VARCHAR(180) NOT NULL, 
	purpose TEXT, 
	focus_json TEXT, 
	priority INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	assigned_to INTEGER NOT NULL, 
	requested_by INTEGER NOT NULL, 
	result_summary TEXT, 
	due_at TIMESTAMP WITHOUT TIME ZONE, 
	completed_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(match_id) REFERENCES matches (id) ON DELETE CASCADE, 
	FOREIGN KEY(target_team_id) REFERENCES teams (id) ON DELETE SET NULL, 
	FOREIGN KEY(assigned_to) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(requested_by) REFERENCES users (id) ON DELETE CASCADE
);



CREATE TABLE scout_reviews (
	id SERIAL NOT NULL, 
	profile_id INTEGER NOT NULL, 
	reviewer_id INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	observed_position VARCHAR(20), 
	technical_rating FLOAT, 
	tactical_rating FLOAT, 
	physical_rating FLOAT, 
	mental_rating FLOAT, 
	current_level FLOAT, 
	potential_score FLOAT, 
	model_fit_score FLOAT, 
	attributes_json TEXT, 
	strengths TEXT, 
	weaknesses TEXT, 
	summary TEXT, 
	recommendation VARCHAR(80), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	submitted_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_scout_review_reviewer UNIQUE (profile_id, reviewer_id), 
	FOREIGN KEY(profile_id) REFERENCES scouted_player_profiles (id) ON DELETE CASCADE, 
	FOREIGN KEY(reviewer_id) REFERENCES users (id) ON DELETE CASCADE
);



CREATE TABLE scouting_list_items (
	id SERIAL NOT NULL, 
	list_id INTEGER NOT NULL, 
	player_id INTEGER NOT NULL, 
	position VARCHAR(20), 
	order_index INTEGER NOT NULL, 
	note TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_scouting_list_player UNIQUE (list_id, player_id), 
	FOREIGN KEY(list_id) REFERENCES scouting_lists (id) ON DELETE CASCADE, 
	FOREIGN KEY(player_id) REFERENCES players (id) ON DELETE CASCADE
);



CREATE TABLE squad_needs (
	id SERIAL NOT NULL, 
	season_id INTEGER NOT NULL, 
	model_role_id INTEGER NOT NULL, 
	need_level VARCHAR(20) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	note TEXT, 
	updated_by INTEGER NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_squad_need_role UNIQUE (season_id, model_role_id), 
	FOREIGN KEY(season_id) REFERENCES seasons (id) ON DELETE CASCADE, 
	FOREIGN KEY(model_role_id) REFERENCES game_model_roles (id) ON DELETE CASCADE, 
	FOREIGN KEY(updated_by) REFERENCES users (id)
);



CREATE TABLE consolidated_player_evaluations (
	id SERIAL NOT NULL, 
	consolidated_report_id INTEGER NOT NULL, 
	player_id INTEGER NOT NULL, 
	final_rating FLOAT, 
	final_recommendation VARCHAR(80), 
	consensus_note TEXT, 
	sample_size INTEGER NOT NULL, 
	dispersion FLOAT, 
	confidence_summary VARCHAR(40), 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_consolidated_player UNIQUE (consolidated_report_id, player_id), 
	FOREIGN KEY(consolidated_report_id) REFERENCES consolidated_reports (id) ON DELETE CASCADE, 
	FOREIGN KEY(player_id) REFERENCES players (id)
);



CREATE TABLE follow_up_history (
	id SERIAL NOT NULL, 
	follow_up_id INTEGER NOT NULL, 
	actor_id INTEGER NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	note TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(follow_up_id) REFERENCES follow_ups (id) ON DELETE CASCADE, 
	FOREIGN KEY(actor_id) REFERENCES users (id)
);



CREATE TABLE player_evaluations (
	id SERIAL NOT NULL, 
	report_id INTEGER NOT NULL, 
	player_id INTEGER NOT NULL, 
	team_id INTEGER NOT NULL, 
	participation_id INTEGER, 
	evaluation_scope VARCHAR(20) NOT NULL, 
	observation_status VARCHAR(30) NOT NULL, 
	general_rating FLOAT, 
	technical_rating FLOAT, 
	tactical_rating FLOAT, 
	physical_rating FLOAT, 
	confidence VARCHAR(20), 
	recommendation VARCHAR(80), 
	strengths TEXT, 
	short_note TEXT, 
	detailed_note TEXT, 
	standout BOOLEAN NOT NULL, 
	pdf_include BOOLEAN NOT NULL, 
	revision INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_report_player UNIQUE (report_id, player_id), 
	FOREIGN KEY(report_id) REFERENCES reports (id) ON DELETE CASCADE, 
	FOREIGN KEY(player_id) REFERENCES players (id), 
	FOREIGN KEY(team_id) REFERENCES teams (id), 
	FOREIGN KEY(participation_id) REFERENCES participations (id) ON DELETE SET NULL
);



CREATE TABLE report_versions (
	id SERIAL NOT NULL, 
	report_id INTEGER NOT NULL, 
	version INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	snapshot_json TEXT NOT NULL, 
	created_by INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_report_version UNIQUE (report_id, version), 
	FOREIGN KEY(report_id) REFERENCES reports (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id)
);



CREATE TABLE scout_mission_targets (
	id SERIAL NOT NULL, 
	mission_id INTEGER NOT NULL, 
	player_id INTEGER NOT NULL, 
	note TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_scout_mission_player UNIQUE (mission_id, player_id), 
	FOREIGN KEY(mission_id) REFERENCES scout_missions (id) ON DELETE CASCADE, 
	FOREIGN KEY(player_id) REFERENCES players (id) ON DELETE CASCADE
);



CREATE TABLE scout_observations (
	id SERIAL NOT NULL, 
	profile_id INTEGER NOT NULL, 
	reviewer_id INTEGER NOT NULL, 
	match_id INTEGER, 
	mission_id INTEGER, 
	source_type VARCHAR(30) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	observed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	observed_position VARCHAR(20), 
	technical_rating FLOAT, 
	tactical_rating FLOAT, 
	physical_rating FLOAT, 
	mental_rating FLOAT, 
	current_level FLOAT, 
	potential_score FLOAT, 
	model_fit_score FLOAT, 
	attributes_json TEXT, 
	strengths TEXT, 
	weaknesses TEXT, 
	summary TEXT, 
	recommendation VARCHAR(80), 
	submitted_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(profile_id) REFERENCES scouted_player_profiles (id) ON DELETE CASCADE, 
	FOREIGN KEY(reviewer_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(match_id) REFERENCES matches (id) ON DELETE SET NULL, 
	FOREIGN KEY(mission_id) REFERENCES scout_missions (id) ON DELETE SET NULL
);



CREATE TABLE documents (
	id SERIAL NOT NULL, 
	report_id INTEGER NOT NULL, 
	report_version_id INTEGER, 
	version INTEGER NOT NULL, 
	document_type VARCHAR(30) NOT NULL, 
	storage_bucket VARCHAR(120), 
	storage_path TEXT, 
	local_path TEXT, 
	checksum VARCHAR(80), 
	size_bytes INTEGER, 
	storage_status VARCHAR(30) NOT NULL, 
	error_message TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_report_document_version_type UNIQUE (report_id, version, document_type), 
	FOREIGN KEY(report_id) REFERENCES reports (id) ON DELETE CASCADE, 
	FOREIGN KEY(report_version_id) REFERENCES report_versions (id) ON DELETE SET NULL
);

