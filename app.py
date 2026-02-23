from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
import stripe
import os
from dotenv import load_dotenv
from services.stripe_service import StripeService
from services.models import BillingAddress, Currency, RecurringInterval

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')

stripe_service = StripeService(
    secret_key=os.getenv('STRIPE_SECRET_KEY'),
    publishable_key=os.getenv('STRIPE_PUBLISHABLE_KEY'),
    webhook_secret=os.getenv('STRIPE_WEBHOOK_SECRET'),
)




# ================================================================== #
# Login decorator                                                      #
# ================================================================== #

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ================================================================== #
# Routes                                                               #
# ================================================================== #

@app.route('/')
@login_required
def index():
    user_email = session.get('user_email')
    subscriptions, queried_customer_ids = stripe_service.get_subscriptions_for_user(user_email, full=False)

    ids = [s.get('id') if isinstance(s, dict) else None for s in subscriptions]
    print(f'Queried customer IDs for {user_email}: {queried_customer_ids}')
    print(f'Fetched {len(subscriptions)} subscriptions for {user_email}: {ids}')

    return render_template(
        'index.html',
        publishable_key=stripe_service.publishable_key,
        user_email=user_email,
        subscriptions=subscriptions,
    )


@app.route('/api/subscriptions')
@login_required
def api_subscriptions():
    """Return subscriptions JSON for the currently logged-in user (debug endpoint)."""
    user_email = session.get('user_email')
    subscriptions, queried_customer_ids = stripe_service.get_subscriptions_for_user(user_email, full=True)
    return jsonify({
        'user_email': user_email,
        'count': len(subscriptions),
        'queried_customer_ids': queried_customer_ids,
        'subscriptions': subscriptions,
    })


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    # TODO: Replace with real authentication logic
    if email and password:
        session['user_email'] = email
        return jsonify({'success': True, 'redirect': '/'}), 200

    return jsonify({'success': False, 'message': 'Invalid email or password'}), 401


@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    data = request.get_json()

    try:
        raw_currency = data.get('currency', 'usd')
        raw_interval = data.get('recurring')
        result = stripe_service.create_checkout_session(
            email=data.get('email'),
            product_name=data.get('productName', 'Default Product'),
            amount_raw=data.get('amount', 0),
            currency=Currency(raw_currency),
            recurring_interval=RecurringInterval(raw_interval) if raw_interval else None,
            success_url=request.host_url + 'success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.host_url,
            billing=BillingAddress.from_dict(data.get('billing')) if data.get('billing') else None,
        )
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except stripe.error.StripeError as exc:
        return jsonify({'error': str(exc)}), 502
    print(jsonify(result))
    return jsonify(result)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/success')
@login_required
def success():
    session_id = request.args.get('session_id')
    details = stripe_service.get_checkout_session_details(session_id) if session_id else {}
    return render_template(
        'success.html',
        session_id=session_id,
        amount=details.get('amount'),
        currency=details.get('currency'),
    )


@app.route('/cancel')
def cancel():
    return 'Subscription cancelled.'


@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe_service.construct_webhook_event(payload, sig_header)
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400

    stripe_service.handle_webhook_event(event)
    return jsonify(success=True)


if __name__ == '__main__':
    app.run(debug=True, port=9001)
