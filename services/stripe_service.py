"""
StripeService - framework-agnostic Stripe integration layer.

Encapsulates all Stripe API calls so the same service can be reused
in Flask, FastAPI, Django REST, or any other project type without
modification.
"""

from datetime import datetime
import stripe

from .models import BillingAddress, Currency, RecurringInterval


# Currencies without minor units (no cents). See Stripe docs for full list.
ZERO_DECIMAL_CURRENCIES = {
    'bif', 'clp', 'djf', 'gnf', 'jpy', 'kmf', 'krw', 'mga', 'pyg',
    'rwf', 'vnd', 'vuv', 'xaf', 'xof', 'xpf'
}


class StripeService:
    """Handles all communication with the Stripe API.

    Usage:
        service = StripeService(
            secret_key="sk_test_...",
            publishable_key="pk_test_...",
            webhook_secret="whsec_...",
        )
    """

    def __init__(self, secret_key: str, publishable_key: str, webhook_secret: str = None):
        self.publishable_key = publishable_key
        self.webhook_secret = webhook_secret
        stripe.api_key = secret_key

    # ------------------------------------------------------------------ #
    # Utility helpers                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def to_minor_unit(amount_major, currency: str) -> int | None:
        """Convert a major-unit decimal amount to the currency's minor unit.

        Examples:
            12.34 USD -> 1234
            1000 JPY -> 1000  (JPY has no minor unit)
        """
        try:
            amt = float(amount_major)
        except (TypeError, ValueError):
            return None

        if currency and currency.lower() in ZERO_DECIMAL_CURRENCIES:
            return int(round(amt))

        return int(round(amt * 100))

    @staticmethod
    def _extract_list_data(obj) -> list:
        """Safely extract `.data` items from Stripe list-like responses."""
        if obj is None:
            return []
        if hasattr(obj, 'data'):
            return obj.data or []
        if isinstance(obj, dict) and 'data' in obj:
            return obj.get('data') or []
        try:
            if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, dict)):
                return list(obj)
        except Exception:
            pass
        return []

    # ------------------------------------------------------------------ #
    # Customers                                                            #
    # ------------------------------------------------------------------ #

    def get_or_create_customer(self, email: str, billing: BillingAddress | None = None) -> str | None:
        """Return a Stripe customer ID for the given email.

        If a customer already exists the billing address is updated (when
        provided).  If no customer exists a new one is created.

        Returns the customer ID, or None on failure.
        """
        billing_dict = billing.to_dict() if billing else {}
        address_payload = {
            'line1': billing_dict.get('line1'),
            'line2': billing_dict.get('line2'),
            'city': billing_dict.get('city'),
            'state': billing_dict.get('state'),
            'postal_code': billing_dict.get('postal_code'),
            'country': billing_dict.get('country'),
        } if billing else None

        try:
            existing = stripe.Customer.list(email=email, limit=1)
            existing_list = self._extract_list_data(existing)

            if existing_list:
                customer = existing_list[0]
                customer_id = getattr(customer, 'id', None)
                if customer_id and billing:
                    try:
                        stripe.Customer.modify(
                            customer_id,
                            address=address_payload,
                            name=billing.name or None,
                        )
                    except Exception as exc:
                        print(f'[StripeService] Failed to update customer address: {exc}')
                return customer_id

            # Create new customer
            create_payload = {'email': email}
            if address_payload:
                create_payload['address'] = address_payload
            if billing and billing.name:
                create_payload['name'] = billing.name

            new_customer = stripe.Customer.create(**create_payload)
            return getattr(new_customer, 'id', None)

        except Exception as exc:
            print(f'[StripeService] Error in get_or_create_customer for {email}: {exc}')
            return None

    # ------------------------------------------------------------------ #
    # Subscriptions                                                        #
    # ------------------------------------------------------------------ #

    def get_subscriptions_for_user(self, user_email: str, full: bool = False) -> tuple[list, list]:
        """Return (subscriptions, queried_customer_ids) for a given email.

        When `full=False` (default) each item is a lightweight summary dict.
        When `full=True` the raw Stripe subscription dicts are returned.
        """
        subscriptions: list = []
        queried_customer_ids: list = []

        if not user_email:
            return subscriptions, queried_customer_ids

        customers = stripe.Customer.list(email=user_email, limit=100)
        customers_list = self._extract_list_data(customers)
        queried_customer_ids = [getattr(c, 'id', None) for c in customers_list]

        for customer in customers_list:
            subs = stripe.Subscription.list(customer=customer.id, limit=100)
            subs_iter = (
                subs.auto_paging_iter()
                if hasattr(subs, 'auto_paging_iter')
                else self._extract_list_data(subs)
            )

            for s in subs_iter:
                if full:
                    subscriptions.append(self._full_subscription(s))
                else:
                    subscriptions.append(self._summary_subscription(s))

        return subscriptions, queried_customer_ids

    def _full_subscription(self, s) -> dict:
        """Return the full Stripe subscription as a dict."""
        try:
            if hasattr(s, 'to_dict'):
                return s.to_dict()
            sub_id = getattr(s, 'id', s)
            try:
                retrieved = stripe.Subscription.retrieve(sub_id)
                return retrieved.to_dict() if hasattr(retrieved, 'to_dict') else dict(retrieved)
            except stripe.error.InvalidRequestError as ire:
                print(f'[StripeService] InvalidRequestError retrieving subscription {sub_id}: {ire}')
                try:
                    retrieved = stripe.Subscription.retrieve(sub_id, expand=[])
                    return retrieved.to_dict() if hasattr(retrieved, 'to_dict') else dict(retrieved)
                except Exception:
                    pass
        except Exception:
            pass

        return {
            'id': getattr(s, 'id', None),
            'status': getattr(s, 'status', None),
            'current_period_end': getattr(s, 'current_period_end', None),
        }

    def _summary_subscription(self, s) -> dict:
        """Return a lightweight subscription summary dict for UI display."""
        items_list = self._extract_list_data(getattr(s, 'items', None))
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
                    print(f'[StripeService] InvalidRequestError retrieving price {price}: {ire}')
                except Exception:
                    pass

        product_name = None
        if price_obj:
            prod = (
                price_obj.get('product')
                if isinstance(price_obj, dict)
                else getattr(price_obj, 'product', None)
            )
            if isinstance(prod, dict):
                product_name = prod.get('name')
            elif prod:
                try:
                    prod_obj = stripe.Product.retrieve(prod)
                    prod_dict = prod_obj.to_dict() if hasattr(prod_obj, 'to_dict') else dict(prod_obj)
                    product_name = prod_dict.get('name')
                except stripe.error.InvalidRequestError as ire:
                    print(f'[StripeService] InvalidRequestError retrieving product {prod}: {ire}')
                except Exception:
                    pass

        period_end = getattr(s, 'current_period_end', None)
        return {
            'id': getattr(s, 'id', None),
            'status': getattr(s, 'status', None),
            'current_period_end': datetime.fromtimestamp(period_end).isoformat() if period_end else None,
            'product_name': product_name,
            'amount': (price_obj.get('unit_amount') / 100) if price_obj and price_obj.get('unit_amount') else None,
            'currency': price_obj.get('currency') if price_obj else None,
            'interval': price_obj.get('recurring', {}).get('interval') if price_obj else None,
        }

    # ------------------------------------------------------------------ #
    # Checkout                                                             #
    # ------------------------------------------------------------------ #

    def create_checkout_session(
        self,
        email: str,
        product_name: str,
        amount_raw,
        currency: Currency | str,
        recurring_interval: RecurringInterval | str | None,
        success_url: str,
        cancel_url: str,
        billing: BillingAddress | None = None,
    ) -> dict:
        """Create a Stripe Checkout Session and return {'url': ..., 'sessionId': ...}.

        Raises ValueError for invalid amounts.
        Raises stripe.error.StripeError on Stripe API errors.
        """
        amount_minor = self.to_minor_unit(amount_raw, currency)
        if amount_minor is None or amount_minor <= 0:
            raise ValueError('Invalid amount')

        price_data = {
            'currency': currency,
            'unit_amount': amount_minor,
            'product_data': {'name': product_name},
        }
        if recurring_interval:
            price_data['recurring'] = {'interval': recurring_interval}

        mode = 'subscription' if recurring_interval else 'payment'
        price = stripe.Price.create(**price_data)

        customer_id = self.get_or_create_customer(email, billing) if email else None

        session_data = {
            'mode': mode,
            'line_items': [{'price': price.id, 'quantity': 1}],
            'payment_method_types': ['card'],
            'billing_address_collection': 'required',
            'locale': 'auto',
            'allow_promotion_codes': False,
            'success_url': success_url,
            'cancel_url': cancel_url,
        }

        if customer_id:
            session_data['customer'] = customer_id
        elif email:
            session_data['customer_email'] = email

        # submit_type is only valid for one-time payments
        if mode == 'payment':
            session_data['submit_type'] = 'pay'

        checkout_session = stripe.checkout.Session.create(**session_data)
        print(f'[StripeService] Created checkout session: {checkout_session.id} for {email}')
        return {'url': checkout_session.url, 'sessionId': checkout_session.id}

    # ------------------------------------------------------------------ #
    # Success page data                                                    #
    # ------------------------------------------------------------------ #

    def get_checkout_session_details(self, session_id: str) -> dict:
        """Return payment details for the success page.

        Returns {'amount': float | None, 'currency': str | None}.
        """
        try:
            stripe.checkout.Session.retrieve(session_id)
            line_items = stripe.checkout.Session.list_line_items(session_id)
            if line_items.data:
                price_obj = stripe.Price.retrieve(line_items.data[0].price.id)
                return {
                    'amount': price_obj.unit_amount / 100,
                    'currency': price_obj.currency.upper(),
                }
        except Exception as exc:
            print(f'[StripeService] Error fetching session {session_id}: {exc}')

        return {'amount': None, 'currency': None}

    # ------------------------------------------------------------------ #
    # Webhooks                                                             #
    # ------------------------------------------------------------------ #

    def construct_webhook_event(self, payload: bytes, sig_header: str):
        """Verify and construct a Stripe webhook event.

        Returns the event object.
        Raises ValueError for invalid payload.
        Raises stripe.error.SignatureVerificationError for invalid signature.
        """
        return stripe.Webhook.construct_event(payload, sig_header, self.webhook_secret)

    # ------------------------------------------------------------------ #
    # Webhook event handlers                                               #
    # ------------------------------------------------------------------ #

    def handle_webhook_event(self, event) -> bool:
        """Dispatch a verified webhook event to the appropriate handler.

        Returns True if the event type was handled, False if unrecognised.
        """
        handlers = {
            'checkout.session.completed': self._on_checkout_session_completed,
            'customer.subscription.updated': self._on_subscription_updated,
            'customer.subscription.deleted': self._on_subscription_deleted,
            'invoice.payment_succeeded': self._on_invoice_payment_succeeded,
            'invoice.payment_failed': self._on_invoice_payment_failed,
        }
        handler = handlers.get(event['type'])
        if handler:
            handler(event)
            return True
        print(f'[StripeService] Unhandled event type: {event["type"]}')
        return False

    def _on_checkout_session_completed(self, event):
        session_obj = event['data']['object']
        print('=== STRIPE HANDLER CHECKOUT COMPLETED ===')
        print(f'Session ID: {session_obj["id"]}')
        print(f'Subscription ID: {session_obj.get("subscription")}')
        print(f'Customer Email: {session_obj.get("customer_email")}')
        print('=========================================')
        # TODO: Store this relationship in your database

    def _on_subscription_updated(self, event):
        subscription = event['data']['object']
        print('=== STRIPE HANDLER SUBSCRIPTION UPDATED ===')
        print(f'Subscription ID: {subscription["id"]}')
        print(f'Customer ID: {subscription["customer"]}')
        print(f'Status: {subscription["status"]}')
        print('============================================')
        # TODO: Update subscription status in your database

    def _on_subscription_deleted(self, event):
        subscription = event['data']['object']
        print('=== STRIPE HANDLER SUBSCRIPTION DELETED ===')
        print(f'Subscription ID: {subscription["id"]}')
        print(f'Customer ID: {subscription["customer"]}')
        print(f'Action: Mark subscription as canceled, revoke access')
        print('============================================')
        # TODO: Mark subscription as canceled in your database, disable access

    def _on_invoice_payment_succeeded(self, event):
        invoice = event['data']['object']
        print('=== STRIPE HANDLER INVOICE PAYMENT SUCCEEDED ===')
        print(f'Invoice ID: {invoice["id"]}')
        print(f'Subscription ID: {invoice.get("subscription")}')
        print(f'Customer ID: {invoice["customer"]}')
        print(f'Amount: {invoice["amount_paid"]} {invoice["currency"].upper()}')
        print('================================================')
        # TODO: Log successful recurring payment in your database

    def _on_invoice_payment_failed(self, event):
        invoice = event['data']['object']
        print('=== STRIPE HANDLER INVOICE PAYMENT FAILED ===')
        print(f'Invoice ID: {invoice["id"]}')
        print(f'Subscription ID: {invoice.get("subscription")}')
        print(f'Customer ID: {invoice["customer"]}')
        print(f'Amount Due: {invoice["amount_due"]} {invoice["currency"].upper()}')
        print(f'Action: Alert user, consider disabling access')
        print('==============================================')
        # TODO: Log failed payment, optionally disable access
