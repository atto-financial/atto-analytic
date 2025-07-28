from flask import Flask, render_template, jsonify
from database import Database
import time
import decimal
from datetime import date, timedelta

app = Flask(__name__)
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
            DATE(created_at) AS transaction_date,
            SUM(CASE WHEN action = 'admin_lend' THEN amount ELSE 0 END) AS total_lent_amount,
            SUM(CASE WHEN action = 'payoff' THEN amount ELSE 0 END) AS total_payoff_amount
        FROM
            public.loan_action_histories
        WHERE
            action IN ('admin_lend', 'payoff') AND
            created_at >= '2025-07-17'
        GROUP BY
            DATE(created_at)
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
            DATE(lah.created_at) AS payoff_date,
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
            lah.created_at >= '2025-07-17'
        GROUP BY
            DATE(lah.created_at)
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
    end_date = date(2025, 7, 28) 

    query = f"""
        WITH all_dates AS (
            SELECT generate_series('{start_date}'::date, '{end_date}'::date, '1 day'::interval)::date AS tracking_date
        ),
        loan_payoffs AS (
            -- Get all distinct loan_ref_ids that have been paid off and the earliest payoff date
            SELECT
                lah.loan_ref_id,
                MIN(lah.created_at::date) AS earliest_payoff_date
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
                MIN(lah.created_at::date) AS earliest_disbursement_date
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
                lr.due_date::date AS loan_due_date,
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
                lr.due_date::date AS tracking_date,
                SUM(lr.approved_amount) AS recorded_due_today_amount
            FROM
                public.loan_requests lr
            WHERE
                lr.approved_amount IS NOT NULL -- Only filter by non-NULL approved_amount
            GROUP BY
                lr.due_date::date
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4370, debug=True)
