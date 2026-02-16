# Stripe POC App

A Python Flask application demonstrating Stripe payment integration with subscription features.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables:
   Create a `.env` file with your Stripe keys:
   ```
   STRIPE_PUBLISHABLE_KEY=pk_test_...
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```

3. Run the app:
   ```bash
   python app.py
   ```

## Features

- Stripe subscription creation
- Payment processing
- Webhook handling for subscription events


Stripe demos and documentation:
https://docs.stripe.com/payments/elements
https://checkout.stripe.dev/elements
https://docs.stripe.com/checkout/embedded/quickstart?lang=python
https://dashboard.stripe.com/acct_1T02ZAFQa34ZXDyi/test/payment-links/create

2 Ways of implementation:
    PreBuilt - https://checkout.stripe.dev/checkout
    Embeded Components - https://checkout.stripe.dev/elements

testing cards:
https://docs.stripe.com/testing#cards
