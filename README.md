# Stripe POC App

A Python Flask application demonstrating Stripe payment integration with subscription and one-time payment features.
The Stripe logic is fully decoupled into a `StripeService` class (`services/stripe_service.py`) so it can be reused
in any project type — Flask MVC, FastAPI WebAPI, Django, etc.

---

## Project Structure

```
app.py                      # Flask routes only — delegates to services
repositories/
    db.py                   # MySQL connection pool (framework-agnostic)
    user_repository.py      # Data-access layer for the users table
services/
    auth_service.py         # Authentication logic (bcrypt hashing, login, register)
    models.py               # Domain enums & dataclasses (Currency, RecurringInterval, BillingAddress)
    stripe_service.py       # All Stripe API communication (framework-agnostic)
migrations/
    001_create_users_table.sql
seed_user.py                # CLI helper to create a test user
templates/
    login.html
    index.html
    success.html
static/
    style.css
    login.css
requirements.txt
.env                        # Not committed — see setup below
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

Or with `uv`:

```bash
uv pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```env
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
SECRET_KEY=your-flask-session-secret

# MySQL
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your-db-password
DB_NAME=stripepoc
```

> `STRIPE_WEBHOOK_SECRET` is provided by the Stripe CLI after running `stripe listen` (see below).

### 3. Create the database

Run the migration script against your MySQL server:

```bash
mysql -u root -p < migrations/001_create_users_table.sql
```

For existing databases, apply incremental migrations:

```bash
mysql -u root -p < migrations/002_add_address_to_users.sql
```

### 4. Seed a test user (optional)

```bash
python seed_user.py
```

You will be prompted for an email and password (min 8 characters). The password is stored as a bcrypt hash.

### 5. Run the Flask app

```bash
python app.py
```

The app starts on **http://localhost:9001**.

---

## Webhook Setup (Local Development)

Stripe webhooks require a running listener that forwards events from Stripe's servers to your local app.
Use the **Stripe CLI** for this.

### Step 1 — Authenticate the Stripe CLI

Open PowerShell and run:

```powershell
& "C:\Program Files (x86)\stripe_1.35.0_windows_x86_64\stripe.exe" login
```

This opens a browser window to authorise the CLI with your Stripe account.

### Step 2 — Start the webhook listener

In a **separate** PowerShell terminal (keep it running alongside the Flask app):

```powershell
& "C:\Program Files (x86)\stripe_1.35.0_windows_x86_64\stripe.exe" listen --forward-to localhost:9001/webhook
```

The CLI will print a webhook signing secret like:

```
> Ready! Your webhook signing secret is whsec_xxxxxxxxxxxxxxxxxxxx
```

Copy that value into your `.env` file as `STRIPE_WEBHOOK_SECRET`, then restart the Flask app.

### Handled webhook events

| Event | Handler |
|---|---|
| `checkout.session.completed` | Mark subscription active, store customer relation |
| `customer.subscription.updated` | Sync subscription status changes |
| `customer.subscription.deleted` | Revoke access, mark as cancelled |
| `invoice.payment_succeeded` | Log successful recurring payment |
| `invoice.payment_failed` | Alert user, optionally disable access |

---

## API Routes

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Dashboard — lists active subscriptions for logged-in user |
| `GET/POST` | `/login` | Login page / authenticate (bcrypt-verified) |
| `POST` | `/register` | Create a new user account (optionally with billing address) |
| `PUT` | `/update-address` | Update billing address for logged-in user |
| `GET` | `/logout` | Clear session and redirect to login |
| `POST` | `/create-checkout-session` | Create a Stripe Checkout session (one-time or subscription) |
| `GET` | `/success` | Post-payment success page |
| `GET` | `/cancel` | Cancellation landing |
| `GET` | `/api/subscriptions` | Debug — returns full subscription JSON for current user |
| `POST` | `/webhook` | Stripe webhook endpoint |

### `POST /create-checkout-session` payload

```json
{
  "email": "user@example.com",
  "productName": "Pro Plan",
  "amount": 29.99,
  "currency": "usd",
  "recurring": "month",
  "billing": {
    "name": "John Doe",
    "line1": "123 Main St",
    "city": "New York",
    "state": "NY",
    "postal_code": "10001",
    "country": "US"
  }
}
```

- Omit `"recurring"` for a one-time payment.
- Supported `recurring` values: `"day"`, `"week"`, `"month"`, `"year"` — backed by the `RecurringInterval` enum.
- Supported `currency` values are defined by the `Currency` enum (e.g. `"usd"`, `"eur"`, `"gbp"`). An unrecognised value returns HTTP 400.

---

## Authentication Architecture

The login system follows a **Repository → Service → Route** layered pattern:

```
app.py (routes)  →  AuthService  →  UserRepository  →  MySQL
```

| Layer | File | Responsibility |
|---|---|---|
| **Repository** | `repositories/user_repository.py` | Raw SQL against the `users` table (parameterised queries) |
| **Service** | `services/auth_service.py` | Password hashing (bcrypt, cost 12), credential verification, registration validation |
| **Route** | `app.py` | HTTP-specific concerns (session, JSON responses) |

### Security best practices applied

- **bcrypt** with adaptive cost factor 12 (resistant to brute-force & rainbow tables)
- Constant-time comparison on login — a dummy bcrypt check runs even when the email is not found (timing-attack mitigation)
- Password minimum length enforced (8 characters)
- Unique constraint on `email` at the database level
- Parameterised queries throughout (no SQL injection)

---

## Reusing StripeService in Other Projects

The service has no Flask dependency — drop it into any Python project.

### Domain models (`services/models.py`)

| Type | Purpose |
|---|---|
| `RecurringInterval` | Enum for billing intervals: `DAY`, `WEEK`, `MONTH`, `YEAR` |
| `Currency` | Enum for Stripe-supported currencies: `USD`, `EUR`, `GBP`, … |
| `BillingAddress` | Dataclass for customer address; converts to/from plain dicts |

Because both enums extend `str` they can be passed directly to the Stripe SDK without calling `.value`.

### Example

```python
from services.stripe_service import StripeService
from services.models import BillingAddress, Currency, RecurringInterval

stripe_service = StripeService(
    secret_key="sk_test_...",
    publishable_key="pk_test_...",
    webhook_secret="whsec_...",
)

# Create a checkout session (typed)
result = stripe_service.create_checkout_session(
    email="user@example.com",
    product_name="Pro Plan",
    amount_raw=29.99,
    currency=Currency.USD,
    recurring_interval=RecurringInterval.MONTH,
    success_url="https://yourapp.com/success",
    cancel_url="https://yourapp.com/",
    billing=BillingAddress(name="John Doe", line1="123 Main St", city="New York", country="US"),
)
print(result["url"])  # Redirect the user here

# Get subscriptions
subscriptions, _ = stripe_service.get_subscriptions_for_user("user@example.com")
```

---

## Testing

Use Stripe's test card numbers — no real charges are made in test mode:

| Card | Scenario |
|---|---|
| `4242 4242 4242 4242` | Successful payment |
| `4000 0025 0000 3155` | Requires 3D Secure authentication |
| `4000 0000 0000 9995` | Payment declined |

Use any future expiry date, any 3-digit CVC, and any postal code.

Full list: https://docs.stripe.com/testing#cards

---

## References

- [Stripe Payment Elements](https://docs.stripe.com/payments/elements)
- [Stripe Checkout Embedded Quickstart (Python)](https://docs.stripe.com/checkout/embedded/quickstart?lang=python)
- [Stripe Checkout Demo — PreBuilt](https://checkout.stripe.dev/checkout)
- [Stripe Checkout Demo — Embedded Components](https://checkout.stripe.dev/elements)
- [Stripe Dashboard — Payment Links](https://dashboard.stripe.com/test/payment-links/create)
