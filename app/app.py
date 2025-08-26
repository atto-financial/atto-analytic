import decimal
from datetime import date, timedelta, datetime
import os
from flask import Flask, render_template, jsonify, request, Response, abort, session, redirect, url_for, flash, make_response
from database import Database
import time
from functools import wraps
from dotenv import load_dotenv
import pandas as pd
from io import BytesIO

load_dotenv()  # Load environment variables from .env file

app = Flask(__name__)
# --- Session Management Configuration ---
# IMPORTANT: This line MUST be here, right after app = Flask(__name__)
# Change this to a strong, random value in production.
# Example for production: import os; app.secret_key = os.environ.get('FLASK_SECRET_KEY')
app.secret_key = os.getenv('AUTH_SECRET')
# ----------------------------------------
db = Database()

# Basic in-memory cache
CACHE = {}
CACHE_TIMEOUT_SECONDS = 300  # Cache data for 5 minutes (adjust as needed)


def get_cached_data(key, fetch_function, *args, **kwargs):
    """
    Retrieves data from cache if fresh, otherwise fetches and caches it.
    """
    now = time.time()
    if key in CACHE and (now - CACHE[key]['timestamp']) < CACHE_TIMEOUT_SECONDS:
        print(f"[{time.ctime()}] Returning cached data for {key}")
        return CACHE[key]['data']

    print(f"[{time.ctime()}] Fetching fresh data for {key}")
    data = fetch_function(*args, **kwargs)
    CACHE[key] = {'data': data, 'timestamp': now}
    return data


# --- Basic Auth Credentials (for demonstration purposes) ---
# In a real application, retrieve these from environment variables or a secure configuration management system
# and hash the password!
USERNAME = os.getenv('AUTH_USERNAME')
PASSWORD = os.getenv('AUTH_PASSWORD')
# -----------------------------------------------------------

# Authentication function (used by the new login system)


def check_credentials(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username == USERNAME and password == PASSWORD

# --- New Authentication Flow ---


@app.before_request
def require_login():
    # Allow access to the login page, logout page, and static files without being logged in
    if request.endpoint == 'static' or \
       request.endpoint == 'login' or \
       request.endpoint == 'logout' or \
       session.get('logged_in'):  # If session indicates logged in
        return  # Allow the request to proceed

    # If not logged in and not trying to access an allowed endpoint, redirect to login
    # Optional: Flash message for user
    flash('Please log in to access this page.', 'info')
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):  # If already logged in, redirect to home
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if check_credentials(username, password):
            session['logged_in'] = True
            flash('Logged in successfully!', 'success')
            # Redirect to home page after successful login
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials. Please try again.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)  # Remove 'logged_in' from session
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/users')
def users():
    query = "SELECT user_id, cid, birth_date, gender, user_status, created_at FROM public.users;"
    users_data = db.fetch_all(query)
    return render_template('users.html', users=users_data)


@app.route('/loan_requests')
def loan_requests():
    query = "SELECT loan_id, request_status, request_amount, approved_amount, due_date, created_at FROM public.loan_requests;"
    loan_data = db.fetch_all(query)
    return render_template('loan_requests.html', loan_requests=loan_data)


@app.route('/api/loan_request_status_data')
def loan_request_status_data():
    query = """
        SELECT request_status, COUNT(*) as count
        FROM public.loan_requests
        GROUP BY request_status;
    """

    def _fetch_status_data():
        status_counts = db.fetch_all(query)
        labels = [row['request_status'] for row in status_counts]
        data = [row['count'] for row in status_counts]
        return {'labels': labels, 'data': data}

    # cached_result = get_cached_data('loan_status_chart', _fetch_status_data)
    return jsonify(_fetch_status_data())


@app.route('/api/daily_loan_transaction_summary')
def daily_loan_transaction_summary():
    query = """
        SELECT
            DATE(created_at + INTERVAL '7 hours') AS transaction_date,
            SUM(CASE WHEN action = 'admin_lend' THEN amount ELSE 0 END) AS total_lent_amount,
            SUM(CASE WHEN action = 'payoff' THEN amount ELSE 0 END) AS total_payoff_amount
        FROM
            public.loan_action_histories
        WHERE
            action IN ('admin_lend', 'payoff') AND
            created_at + INTERVAL '7 hours' >= '2025-07-17'
        GROUP BY
            DATE(created_at + INTERVAL '7 hours')
        ORDER BY
            transaction_date ASC;
    """

    def _fetch_daily_summary_data():
        summary_data = db.fetch_all(query)
        for row in summary_data:
            if 'total_lent_amount' in row and row['total_lent_amount'] is not None:
                row['total_lent_amount'] = float(row['total_lent_amount'])
            if 'total_payoff_amount' in row and row['total_payoff_amount'] is not None:
                row['total_payoff_amount'] = float(row['total_payoff_amount'])
            if 'transaction_date' in row and row['transaction_date'] is not None:
                row['transaction_date'] = row['transaction_date'].isoformat()
        return summary_data

    # cached_result = get_cached_data(
        # 'daily_loan_summary_chart', _fetch_daily_summary_data)
    return jsonify(_fetch_daily_summary_data())


@app.route('/api/daily_payoff_details')
def daily_payoff_details():
    query = """
        SELECT
            DATE(lah.created_at + INTERVAL '7 hours') AS payoff_date,
            COALESCE(SUM(lr.approved_amount), 0.00) AS total_principal_paid,
            COALESCE(SUM(iah.total_amount), 0.00) AS total_interest_paid,
            COALESCE(SUM(fah.fee), 0.00) AS total_initial_fee_paid,
            COALESCE(SUM(fah.total_amount), 0.00) AS total_fine_amount_paid,
            COALESCE(SUM(cfh.total_amount), 0.00) AS total_collection_fee_paid,
            SUM(lah.amount) AS total_actual_payoff_from_action
        FROM
            public.loan_action_histories lah
        LEFT JOIN
            public.loan_requests lr ON lah.loan_ref_id = lr.loan_ref_id
        LEFT JOIN
            (SELECT loan_ref_id, SUM(total_amount) AS total_amount FROM public.interest_adjustment_histories GROUP BY loan_ref_id) iah
            ON lah.loan_ref_id = iah.loan_ref_id
        LEFT JOIN
            (SELECT loan_ref_id, SUM(fee) AS fee, SUM(total_amount) AS total_amount FROM public.fine_adjustment_histories GROUP BY loan_ref_id) fah
            ON lah.loan_ref_id = fah.loan_ref_id
        LEFT JOIN
            (SELECT loan_ref_id, SUM(total_amount) AS total_amount FROM public.collection_fee_histories GROUP BY loan_ref_id) cfh
            ON lah.loan_ref_id = cfh.loan_ref_id
        WHERE
            lah.action = 'payoff' AND
            lah.created_at + INTERVAL '7 hours' >= '2025-07-17'
        GROUP BY
            DATE(lah.created_at + INTERVAL '7 hours')
        ORDER BY
            payoff_date ASC;
    """

    def _fetch_daily_payoff_details_data():
        details_data = db.fetch_all(query)
        # Convert Decimals and dates to serializable formats
        import decimal  # Import decimal module here
        for row in details_data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):  # Explicitly check for Decimal type
                    row[key] = float(value)
                # Date objects
                elif value is not None and hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
                # No 'else' needed for float/int, as they are already JSON serializable
        return details_data

    # cached_result = get_cached_data(
        # 'daily_payoff_details_chart', _fetch_daily_payoff_details_data)
    return jsonify(_fetch_daily_payoff_details_data())


# --- NEW ROUTES FOR RAW DATA TABLES ---

@app.route('/accounting_tracks')
def accounting_tracks():
    query = """
        SELECT created_at, today_lent_amount, today_cash_amount, in_due_amount,
               in_due_principal, due_date_amount, default_amount,
               default_principal_amount, today_paid_amount, today_paid_principal_amount,
               today_paid_margin_amount, operational_cost_amount, operational_cost_desc
        FROM public.accouting_tracks;
    """

    def _fetch_accounting_tracks_data():
        data = db.fetch_all(query)
        for row in data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
                elif value is not None and hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
        return data

    tracks_data = get_cached_data(
        'accounting_tracks_table', _fetch_accounting_tracks_data)
    return render_template('accounting_tracks.html', accounting_tracks=tracks_data)


@app.route('/answers')
def answers():
    query = """
        SELECT answer_id, session_id, user_id, feature_id, model_id,
               answer, ml_artifact, approval_loan_status, updated_at, created_at
        FROM public.answers;
    """

    def _fetch_answers_data():
        data = db.fetch_all(query)
        for row in data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
                elif value is not None and hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
                elif isinstance(value, dict) or isinstance(value, list):  # For JSONB
                    # Convert JSONB to string for display
                    row[key] = str(value)
        return data

    answers_data = get_cached_data('answers_table', _fetch_answers_data)
    return render_template('answers.html', answers=answers_data)

# --- REPEAT THE PATTERN FOR ALL REMAINING TABLES BELOW ---


@app.route('/collection_fee_histories')
def collection_fee_histories():
    query = """
        SELECT collection_fee_id, user_id, loan_ref_id, loan_due_date, round,
               total_loan_amount, total_amount, created_at
        FROM public.collection_fee_histories;
    """

    def _fetch_data():
        data = db.fetch_all(query)
        for row in data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
                elif value is not None and hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
        return data
    data = get_cached_data('collection_fee_histories_table', _fetch_data)
    return render_template('collection_fee_histories.html', data=data)


@app.route('/connect_platforms')
def connect_platforms():
    query = """
        SELECT user_id, line_user_id, line_latest_profile_display,
               line_latest_profile_picture, line_is_blocked, updated_at, created_at
        FROM public.connect_platforms;
    """

    def _fetch_data():
        data = db.fetch_all(query)
        for row in data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
                elif value is not None and hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
        return data
    data = get_cached_data('connect_platforms_table', _fetch_data)
    return render_template('connect_platforms.html', data=data)


@app.route('/consents')
def consents():
    query = """
        SELECT consent_id, user_id, version, content, allowed, created_at
        FROM public.consents;
    """

    def _fetch_data():
        data = db.fetch_all(query)
        for row in data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
                elif value is not None and hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
        return data
    data = get_cached_data('consents_table', _fetch_data)
    return render_template('consents.html', data=data)


@app.route('/default_configs')
def default_configs():
    query = """
        SELECT c_key, c_type, c_value
        FROM public.default_configs;
    """

    def _fetch_data():
        data = db.fetch_all(query)
        for row in data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
                elif value is not None and hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
        return data
    data = get_cached_data('default_configs_table', _fetch_data)
    return render_template('default_configs.html', data=data)


@app.route('/features')
def features():
    query = """
        SELECT feature_id, feature_slug, title, description,
               questions_n_choices, removed, updated_by, created_by, created_at, updated_at
        FROM public.features;
    """

    def _fetch_data():
        data = db.fetch_all(query)
        for row in data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
                elif value is not None and hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
                elif isinstance(value, dict) or isinstance(value, list):  # For JSONB
                    row[key] = str(value)
        return data
    data = get_cached_data('features_table', _fetch_data)
    return render_template('features.html', data=data)


@app.route('/fine_adjustment_histories')
def fine_adjustment_histories():
    query = """
        SELECT fine_adj_id, user_id, loan_ref_id, fee, total_amount, created_at, total_loan_amount
        FROM public.fine_adjustment_histories;
    """

    def _fetch_data():
        data = db.fetch_all(query)
        for row in data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
                elif value is not None and hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
        return data
    data = get_cached_data('fine_adjustment_histories_table', _fetch_data)
    return render_template('fine_adjustment_histories.html', data=data)


@app.route('/interest_adjustment_histories')
def interest_adjustment_histories():
    query = """
        SELECT interest_adj_id, user_id, loan_ref_id, principle, interest_rate,
               total_amount, created_at, total_loan_amount
        FROM public.interest_adjustment_histories;
    """

    def _fetch_data():
        data = db.fetch_all(query)
        for row in data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
                elif value is not None and hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
        return data
    data = get_cached_data('interest_adjustment_histories_table', _fetch_data)
    return render_template('interest_adjustment_histories.html', data=data)


@app.route('/loan_action_histories')
def loan_action_histories():
    query = """
        SELECT action_id, user_id, loan_ref_id, action, amount, latest_payoff_score,
               latest_payoff_count, attach, accepted, note, updated_by, updated_at,
               created_by, created_at
        FROM public.loan_action_histories;
    """

    def _fetch_data():
        data = db.fetch_all(query)
        for row in data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
                elif value is not None and hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
        return data
    data = get_cached_data('loan_action_histories_table', _fetch_data)
    return render_template('loan_action_histories.html', data=data)


@app.route('/loan_summary_statuses')
def loan_summary_statuses():
    query = """
        SELECT user_id, loanable, fee_rate, interest_rate, payoff_count, principle,
               total_loan_amount, loan_status, payoff_score, max_loan_amount,
               max_payoff_day, cool_down_payoff_count, cool_down_payoff_date, updated_at
        FROM public.loan_summary_statuses;
    """

    def _fetch_data():
        data = db.fetch_all(query)
        for row in data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
                elif value is not None and hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
        return data
    data = get_cached_data('loan_summary_statuses_table', _fetch_data)
    return render_template('loan_summary_statuses.html', data=data)


@app.route('/model_predicts')
def model_predicts():
    query = """
        SELECT feature_id, session_id, user_id, model_id, default_probability,
               model_prediction, adjust_prediction, data_set, nextgen_prediction,
               nextgen_adjprediction, updated_at, created_at
        FROM public.model_predicts;
    """

    def _fetch_data():
        data = db.fetch_all(query)
        for row in data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
                elif value is not None and hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
                elif isinstance(value, dict) or isinstance(value, list):  # For JSONB
                    row[key] = str(value)
        return data
    data = get_cached_data('model_predicts_table', _fetch_data)
    return render_template('model_predicts.html', data=data)


@app.route('/models')
def models():
    query = """
        SELECT model_id, model_slug, title, description, removed,
               updated_by, updated_at, created_by, created_at
        FROM public.models;
    """

    def _fetch_data():
        data = db.fetch_all(query)
        for row in data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
                elif value is not None and hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
        return data
    data = get_cached_data('models_table', _fetch_data)
    return render_template('models.html', data=data)


@app.route('/user_academics')
def user_academics():
    query = """
        SELECT user_id, name, academic_years, start_date, end_date,
               card_expried_date, student_credential_img, created_at, updated_at
        FROM public.user_academics;
    """

    def _fetch_data():
        data = db.fetch_all(query)
        for row in data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
                elif value is not None and hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
        return data
    data = get_cached_data('user_academics_table', _fetch_data)
    return render_template('user_academics.html', data=data)


@app.route('/user_addresses')
def user_addresses():
    query = """
        SELECT user_id, address, subdistrict, district, province, zipcode, updated_at
        FROM public.user_addresses;
    """

    def _fetch_data():
        data = db.fetch_all(query)
        for row in data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
                elif value is not None and hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
        return data
    data = get_cached_data('user_addresses_table', _fetch_data)
    return render_template('user_addresses.html', data=data)


@app.route('/user_occupations')
def user_occupations():
    query = """
        SELECT user_id, occupation_name, monthly_income, updated_at
        FROM public.user_occupations;
    """

    def _fetch_data():
        data = db.fetch_all(query)
        for row in data:
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    row[key] = float(value)
                elif value is not None and hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
        return data
    data = get_cached_data('user_occupations_table', _fetch_data)
    return render_template('user_occupations.html', data=data)


@app.route('/api/daily_loan_situations')
def daily_loan_situations():
    # Set your desired date range
    start_date = date(2025, 7, 17)
    end_date = date.today()

    query = f"""
        WITH all_dates AS (
            SELECT generate_series('{start_date}'::date, '{end_date}'::date, '1 day'::interval)::date AS tracking_date
        ),
        loan_payoffs AS (
            -- Get all distinct loan_ref_ids that have been paid off and the earliest payoff date
            SELECT
                lah.loan_ref_id,
                MIN(lah.created_at + INTERVAL '7 hours') AS earliest_payoff_date
            FROM
                public.loan_action_histories lah
            WHERE
                lah.action = 'payoff'
            GROUP BY
                lah.loan_ref_id
        ),
        loan_disbursements AS (
            -- Get all distinct loan_ref_ids that have been actually disbursed (lent out)
            SELECT
                lah.loan_ref_id,
                MIN(lah.created_at + INTERVAL '7 hours') AS earliest_disbursement_date
            FROM
                public.loan_action_histories lah
            WHERE
                lah.action = 'admin_lend'
            GROUP BY
                lah.loan_ref_id
        ),
        -- CTE for Outstanding Amounts: Filters loans by disbursement date <= tracking_date and not paid off by tracking_date.
        -- NO FILTER on request_status here.
        outstanding_loan_data AS (
            SELECT
                lr.loan_ref_id,
                lr.approved_amount,
                lr.due_date + INTERVAL '7 hours' AS loan_due_date,
                ld.earliest_disbursement_date AS disbursed_at, -- Use disbursement date for tracking
                lpo.earliest_payoff_date
            FROM
                public.loan_requests lr
            INNER JOIN -- Only include loans that have been disbursed
                loan_disbursements ld ON lr.loan_ref_id = ld.loan_ref_id
            LEFT JOIN
                loan_payoffs lpo ON lr.loan_ref_id = lpo.loan_ref_id
            WHERE
                lr.approved_amount IS NOT NULL
        ),
        -- Aggregate Outstanding Amounts per tracking_date
        aggregated_outstanding AS (
            SELECT
                ad.tracking_date,
                SUM(CASE
                    -- Due Today (Outstanding): loan is due on tracking_date AND was disbursed on or before tracking_date
                    -- AND NOT paid off (earliest_payoff_date is NULL OR after tracking_date)
                    WHEN old.loan_due_date = ad.tracking_date AND old.disbursed_at <= ad.tracking_date AND (old.earliest_payoff_date IS NULL OR old.earliest_payoff_date > ad.tracking_date)
                    THEN old.approved_amount ELSE 0
                END) AS due_today_amount,
                SUM(CASE
                    -- Due Future (Outstanding): due date in future AND was disbursed on or before tracking_date
                    -- AND NOT paid off (earliest_payoff_date is NULL OR after tracking_date)
                    WHEN old.loan_due_date > ad.tracking_date AND old.disbursed_at <= ad.tracking_date AND (old.earliest_payoff_date IS NULL OR old.earliest_payoff_date > ad.tracking_date)
                    THEN old.approved_amount ELSE 0
                END) AS due_future_amount,
                SUM(CASE
                    -- Overdue (Outstanding): due date in past AND was disbursed on or before tracking_date
                    -- AND NOT paid off (earliest_payoff_date is NULL OR after tracking_date)
                    WHEN old.loan_due_date < ad.tracking_date AND old.disbursed_at <= ad.tracking_date AND (old.earliest_payoff_date IS NULL OR old.earliest_payoff_date > ad.tracking_date)
                    THEN old.approved_amount ELSE 0
                END) AS overdue_amount
            FROM
                all_dates ad
            CROSS JOIN
                outstanding_loan_data old
            GROUP BY
                ad.tracking_date
        ),
        -- CTE for Recorded Due Today: Only considers loans with a due_date equal to tracking_date and a non-NULL approved_amount.
        -- NO FILTER on request_status here.
        recorded_due_today AS (
            SELECT
                lr.due_date + INTERVAL '7 hours' AS tracking_date,
                SUM(lr.approved_amount) AS recorded_due_today_amount
            FROM
                public.loan_requests lr
            WHERE
                lr.approved_amount IS NOT NULL -- Only filter by non-NULL approved_amount
            GROUP BY
                lr.due_date + INTERVAL '7 hours'
        )
        SELECT
            ad.tracking_date,
            COALESCE(ago.due_today_amount, 0.00) AS due_today_amount,
            COALESCE(ago.due_future_amount, 0.00) AS due_future_amount,
            COALESCE(ago.overdue_amount, 0.00) AS overdue_amount,
            COALESCE(rdt.recorded_due_today_amount, 0.00) AS recorded_due_today_amount
        FROM
            all_dates ad
        LEFT JOIN
            aggregated_outstanding ago ON ad.tracking_date = ago.tracking_date
        LEFT JOIN
            recorded_due_today rdt ON ad.tracking_date = rdt.tracking_date
        ORDER BY
            ad.tracking_date ASC;
    """

    def _fetch_daily_loan_situations_data():
        data = db.fetch_all(query)
        processed_data = []
        for row in data:
            processed_row = {}
            for key, value in row.items():
                if isinstance(value, decimal.Decimal):
                    processed_row[key] = float(value)
                elif value is not None and hasattr(value, 'isoformat'):
                    processed_row[key] = value.isoformat()
                else:
                    processed_row[key] = value
            processed_data.append(processed_row)
        return processed_data

    return jsonify(_fetch_daily_loan_situations_data())

# The new endpoint to generate and download the Excel file
@app.route('/debtor-list')
def debtor_list():
    # Authentication check before serving the file
    if not session.get('logged_in'):
        flash('Please log in to access this page.', 'info')
        return redirect(url_for('login'))

    queries = {
        # --- (Existing sheets) ---
        'Due date do not payoff': """
            SELECT
                cnp.line_latest_profile_display,
                lss.principle,
                lss.total_loan_amount,
                lr.due_date,
                cnp.line_user_id
            FROM users u
            INNER JOIN connect_platforms cnp ON cnp.user_id = u.user_id
            INNER JOIN loan_requests lr ON lr.user_id = u.user_id
            INNER JOIN loan_summary_statuses lss ON lss.user_id = u.user_id
            WHERE 
                DATE(lr.due_date) = DATE(CURRENT_DATE - INTERVAL '7 hours')
                AND lr.request_status = 'approved';
        """,
        'Late pay': """
            SELECT
                cnp.line_latest_profile_display,
                lss.principle,
                lss.total_loan_amount,
                lr.due_date,
                cnp.line_user_id
            FROM users u
            INNER JOIN connect_platforms cnp ON cnp.user_id = u.user_id
            INNER JOIN loan_requests lr ON lr.user_id = u.user_id
            INNER JOIN loan_summary_statuses lss ON lss.user_id = u.user_id
            WHERE 
                DATE(lr.due_date) < DATE(CURRENT_DATE - INTERVAL '7 hours')
                AND lr.request_status = 'approved'
                AND lss.loan_status = 'healthy';
        """,
        'Overdue': """
            SELECT
                cnp.line_latest_profile_display,
                lss.principle,
                lss.total_loan_amount,
                lr.due_date,
                cnp.line_user_id
            FROM users u
            INNER JOIN connect_platforms cnp ON cnp.user_id = u.user_id
            INNER JOIN loan_requests lr ON lr.user_id = u.user_id
            INNER JOIN loan_summary_statuses lss ON lss.user_id = u.user_id
            WHERE 
                DATE(lr.due_date) < DATE(CURRENT_DATE - INTERVAL '7 hours')
                AND lr.request_status = 'approved'
                AND lss.loan_status = 'loan_overdue';
        """,
        'NPL': """
            SELECT
                cnp.line_latest_profile_display,
                lss.principle,
                lss.total_loan_amount,
                lr.due_date,
                cnp.line_user_id
            FROM users u
            INNER JOIN connect_platforms cnp ON cnp.user_id = u.user_id
            INNER JOIN loan_requests lr ON lr.user_id = u.user_id
            INNER JOIN loan_summary_statuses lss ON lss.user_id = u.user_id
            WHERE 
                DATE(lr.due_date) < DATE(CURRENT_DATE - INTERVAL '7 hours')
                AND lr.request_status = 'approved'
                AND lss.loan_status = 'npl';
        """,
        # --- START NEW SHEET ---
        'All Active Loans': """
            SELECT
                cnp.line_latest_profile_display,
                lss.principle,
                lss.total_loan_amount,
                lr.due_date,
                cnp.line_user_id,
                lss.loan_status,
                lr.request_amount,
                lr.request_status
            FROM users u
            INNER JOIN connect_platforms cnp ON cnp.user_id = u.user_id
            INNER JOIN loan_requests lr ON lr.user_id = u.user_id
            INNER JOIN loan_summary_statuses lss ON lss.user_id = u.user_id
            WHERE 
                lr.request_status = 'approved'
            ORDER BY lr.due_date ASC;
        """
        # --- END NEW SHEET ---
    }

    # Create an in-memory buffer to hold the Excel file
    excel_buffer = BytesIO()

    # Use a Pandas ExcelWriter to write to the buffer
    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
        for sheet_name, query in queries.items():
            try:
                # Fetch data from the database
                data = db.fetch_all(query)
                
                # Pre-process the data to remove timezone information
                for row in data:
                    if 'due_date' in row and row['due_date'] is not None and pd.to_datetime(row['due_date']).tz is not None:
                        row['due_date'] = pd.to_datetime(row['due_date']).tz_localize(None)
                
                # Convert the list of dictionaries to a Pandas DataFrame
                df = pd.DataFrame(data)
                
                # Write the DataFrame to a specific sheet
                df.to_excel(writer, sheet_name=sheet_name, index=False)
            except Exception as e:
                # Log the error but continue
                print(f"Error generating sheet '{sheet_name}': {e}")
                
                # Create an error DataFrame for this sheet
                error_df = pd.DataFrame([{'Error': f"Could not generate this sheet due to an error: {e}"}])
                error_df.to_excel(writer, sheet_name=sheet_name, index=False)

    # Move the buffer's cursor to the beginning
    excel_buffer.seek(0)
    
    # Generate a dynamic filename with the current date and time
    now = datetime.now()
    timestamp_str = now.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"debtor_list_{timestamp_str}.xlsx"
    
    # Create the HTTP response with the Excel file
    response = make_response(excel_buffer.getvalue())
    
    # Set the headers for file download
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    response.headers['Content-type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    return response


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4370, debug=True)
