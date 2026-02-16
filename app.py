from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from datetime import datetime
import stripe
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
stripe_publishable_key = os.getenv('STRIPE_PUBLISHABLE_KEY')


def _extract_list_data(obj):
    """Safely extract `.data` items from Stripe list-like responses.

    Returns a list. Handles ListObject with `.data`, plain dicts with 'data',
    or any iterable. If `obj` is unexpected, returns an empty list.
    """
    if obj is None:
        return []
    # Stripe ListObject usually exposes .data
    if hasattr(obj, 'data'):
        return obj.data or []
    # Dict-like
    if isinstance(obj, dict) and 'data' in obj:
        return obj.get('data') or []
    # If it's iterable (generator, list, etc.) convert to list
    try:
        if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, dict)):
            return list(obj)
    except Exception:
        pass
    return []

def _get_subscriptions_for_user(user_email, full=False):
    subscriptions = []
    queried_customer_ids = []
    
    if not user_email:
        return subscriptions, queried_customer_ids

    # 1. Fetch all customers with this email
    customers = stripe.Customer.list(email=user_email, limit=100)
    customers_list = _extract_list_data(customers)
    queried_customer_ids = [getattr(c, 'id', None) for c in customers_list]

    for customer in customers_list:
        # 2. List subscriptions for this customer (no deep expansions)
        subs = stripe.Subscription.list(customer=customer.id, limit=100)
        subs_iter = subs.auto_paging_iter() if hasattr(subs, 'auto_paging_iter') else _extract_list_data(subs)

        for s in subs_iter:
            if full:
                # Return a full subscription dict when possible, but handle InvalidRequestError
                try:
                    if hasattr(s, 'to_dict'):
                        full_sub = s.to_dict()
                    else:
                        sub_id = getattr(s, 'id', s)
                        try:
                            retrieved = stripe.Subscription.retrieve(sub_id)
                            full_sub = retrieved.to_dict() if hasattr(retrieved, 'to_dict') else dict(retrieved)
                        except stripe.error.InvalidRequestError as ire:
                            print(f'Stripe InvalidRequestError retrieving subscription {sub_id}: {ire}')
                            try:
                                retrieved = stripe.Subscription.retrieve(sub_id, expand=[])
                                full_sub = retrieved.to_dict() if hasattr(retrieved, 'to_dict') else dict(retrieved)
                            except Exception:
                                full_sub = s if isinstance(s, dict) else {
                                    'id': getattr(s, 'id', None),
                                    'status': getattr(s, 'status', None),
                                    'current_period_end': getattr(s, 'current_period_end', None),
                                }
                except Exception:
                    full_sub = s if isinstance(s, dict) else {
                        'id': getattr(s, 'id', None),
                        'status': getattr(s, 'status', None),
                        'current_period_end': getattr(s, 'current_period_end', None),
                    }
                subscriptions.append(full_sub)
            else:
                # Build a lightweight summary for the UI
                items_list = _extract_list_data(getattr(s, 'items', None))
                item = items_list[0] if items_list else None

                price_obj = None
                if item:
                    price = item.get('price') if isinstance(item, dict) else getattr(item, 'price', None)
                    if isinstance(price, dict):
                        price_obj = price
                    elif price:
                        try:
                            p = stripe.Price.retrieve(price)
                            price_obj = p.to_dict() if hasattr(p, 'to_dict') else dict(p)
                        except stripe.error.InvalidRequestError as ire:
                            print(f'Stripe InvalidRequestError retrieving price {price}: {ire}')
                            price_obj = None
                        except Exception:
                            price_obj = None

                product_name = None
                if price_obj:
                    prod = price_obj.get('product') if isinstance(price_obj, dict) else getattr(price_obj, 'product', None)
                    if isinstance(prod, dict):
                        product_name = prod.get('name')
                    elif prod:
                        try:
                            prod_obj = stripe.Product.retrieve(prod)
                            prod_dict = prod_obj.to_dict() if hasattr(prod_obj, 'to_dict') else dict(prod_obj)
                            product_name = prod_dict.get('name')
                        except stripe.error.InvalidRequestError as ire:
                            print(f'Stripe InvalidRequestError retrieving product {prod}: {ire}')
                            product_name = None
                        except Exception:
                            product_name = None

                subscriptions.append({
                    'id': getattr(s, 'id', None),
                    'status': getattr(s, 'status', None),
                    'current_period_end': datetime.fromtimestamp(s.current_period_end).isoformat() if getattr(s, 'current_period_end', None) else None,
                    'product_name': product_name,
                    'amount': (price_obj.get('unit_amount') / 100) if price_obj and price_obj.get('unit_amount') else None,
                    'currency': price_obj.get('currency') if price_obj else None,
                    'interval': price_obj.get('recurring', {}).get('interval') if price_obj else None,
                })

    return subscriptions, queried_customer_ids

# ============== Webhook Event Handlers ==============

def handle_checkout_session_completed(event):
    """Handle checkout session completion"""
    session_obj = event['data']['object']
    session_id = session_obj['id']
    subscription_id = session_obj.get('subscription')
    customer_email = session_obj.get('customer_email')
    
    print(f'=== STRIPE HANDLER CHECKOUT COMPLETED ===')
    print(f'Session ID: {session_id}')
    print(f'Subscription ID: {subscription_id}')
    print(f'Customer Email: {customer_email}')
    print(f'=========================')
    # TODO: Store this relationship in database

def handle_subscription_updated(event):
    """Handle subscription updates"""
    subscription = event['data']['object']
    subscription_id = subscription['id']
    customer_id = subscription['customer']
    status = subscription['status']
    session_id = subscription.get('client_secret', 'N/A')  # Try to get session info
    
    print(f'=== STRIPE HANDLER SUBSCRIPTION UPDATED ===')
    print(f'Subscription ID: {subscription_id}')
    print(f'Customer ID: {customer_id}')
    print(f'Session ID: {session_id}')
    print(f'Status: {status}')
    print(f'============================')
    # TODO: Update subscription status in database

def handle_subscription_deleted(event):
    """Handle subscription cancellation"""
    subscription = event['data']['object']
    subscription_id = subscription['id']
    customer_id = subscription['customer']
    session_id = subscription.get('client_secret', 'N/A')  # Try to get session info
    
    print(f'=== STRIPE HANDLER SUBSCRIPTION DELETED ===')
    print(f'Subscription ID: {subscription_id}')
    print(f'Customer ID: {customer_id}')
    print(f'Session ID: {session_id}')
    print(f'Action: Mark subscription as canceled, revoke access')
    print(f'============================')
    # TODO: Mark subscription as canceled in database, disable access

def handle_invoice_payment_succeeded(event):
    """Handle successful recurring payments"""
    invoice = event['data']['object']
    invoice_id = invoice['id']
    customer_id = invoice['customer']
    subscription_id = invoice.get('subscription')
    amount = invoice['amount_paid']
    currency = invoice['currency']
    
    print(f'=== STRIPE HANDLER INVOICE PAYMENT SUCCEEDED ===')
    print(f'Invoice ID: {invoice_id}')
    print(f'Subscription ID: {subscription_id}')
    print(f'Customer ID: {customer_id}')
    print(f'Amount: {amount} {currency.upper()}')
    print(f'==================================')
    # TODO: Log successful recurring payment in database

def handle_invoice_payment_failed(event):
    """Handle failed recurring payments"""
    invoice = event['data']['object']
    invoice_id = invoice['id']
    customer_id = invoice['customer']
    subscription_id = invoice.get('subscription')
    amount = invoice['amount_due']
    currency = invoice['currency']
    
    print(f'=== STRIPE HANDLER INVOICE PAYMENT FAILED ===')
    print(f'Invoice ID: {invoice_id}')
    print(f'Subscription ID: {subscription_id}')
    print(f'Customer ID: {customer_id}')
    print(f'Amount Due: {amount} {currency.upper()}')
    print(f'Action: Alert user, consider disabling access')
    print(f'================================')
    # TODO: Log failed payment, optionally disable access

# Event handler mapping
EVENT_HANDLERS = {
    'checkout.session.completed': handle_checkout_session_completed,
    'customer.subscription.updated': handle_subscription_updated,
    'customer.subscription.deleted': handle_subscription_deleted,
    'invoice.payment_succeeded': handle_invoice_payment_succeeded,
    'invoice.payment_failed': handle_invoice_payment_failed,
}

# ============== Login Decorator ==============

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required
def index():
    user_email = session.get('user_email')
    subscriptions = []

    subscriptions, queried_customer_ids = _get_subscriptions_for_user(user_email, full=False)

    # Debug logging: show how many subscriptions we found and their IDs
    try:
        ids = [s.get('id') if isinstance(s, dict) else None for s in subscriptions]
    except Exception:
        ids = []
    print(f'Queried customer IDs for {user_email}: {queried_customer_ids}')
    print(f'Fetched {len(subscriptions)} subscriptions for {user_email}: {ids}')

    return render_template('index.html', publishable_key=stripe_publishable_key, user_email=user_email, subscriptions=subscriptions)


@app.route('/api/subscriptions')
@login_required
def api_subscriptions():
    """Return subscriptions JSON for the currently logged-in user (debug endpoint)."""
    user_email = session.get('user_email')
    subscriptions = []
    subscriptions, queried_customer_ids = _get_subscriptions_for_user(user_email, full=True)
    return jsonify({'user_email': user_email, 'count': len(subscriptions), 'queried_customer_ids': queried_customer_ids, 'subscriptions': subscriptions})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    # Handle POST request for login
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    # TODO: Add your authentication logic here
    # This is a placeholder - implement actual user authentication
    if email and password:
        # Example: validate against a database
        session['user_email'] = email
        return jsonify({'success': True, 'redirect': '/'}), 200
    else:
        return jsonify({'success': False, 'message': 'Invalid email or password'}), 401

@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    data = request.get_json()
    email = data.get('email')
    product_name = data.get('productName', 'Default Product')
    amount = data.get('amount', 0) 
    currency = data.get('currency', 'usd')
    recurring_interval = data.get('recurring')
    
    # Create a price
    price_data = {
        'currency': currency,
        'unit_amount': amount,
        'product_data': {'name': product_name},
    }
    
    if recurring_interval:
        price_data['recurring'] = {'interval': recurring_interval}
        mode = 'subscription'
    else:
        mode = 'payment'
    
    price = stripe.Price.create(**price_data)
    
    # Create a checkout session
    session_data = {
        'mode': mode,
        'line_items': [
            {
                'price': price.id,
                'quantity': 1,
            },
        ],
        'success_url': request.host_url + 'success?session_id={CHECKOUT_SESSION_ID}',
        'cancel_url': request.host_url, # + 'cancel',
    }
    
    if email:
        session_data['customer_email'] = email
    
    session = stripe.checkout.Session.create(**session_data)
    print(f'Created checkout session: {session.id} for email: {email} with url: {session.url}')
    return jsonify({'url': session.url, 'sessionId': session.id})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/success')
@login_required
def success():
    session_id = request.args.get('session_id')
    amount = None
    currency = None
    
    if session_id:
        try:
            # Fetch the checkout session from Stripe
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            
            # Get the line items to extract amount and currency
            line_items = stripe.checkout.Session.list_line_items(session_id)
            if line_items.data:
                line_item = line_items.data[0]
                price_obj = stripe.Price.retrieve(line_item.price.id)
                amount = price_obj.unit_amount / 100  # Convert from cents
                currency = price_obj.currency.upper()
        except Exception as e:
            print(f'Error fetching session: {e}')
    
    return render_template('success.html', session_id=session_id, amount=amount, currency=currency)

@app.route('/cancel')
def cancel():
    return 'Subscription cancelled.'

@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400

    # Dispatch event to appropriate handler
    handler = EVENT_HANDLERS.get(event['type'])
    if handler:
        handler(event)
    else:
        print(f'Unhandled event type: {event["type"]}')

    return jsonify(success=True)

if __name__ == '__main__':
    app.run(debug=True)