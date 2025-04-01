import stripe

stripe_customer_id = "cus_55l9HcgrPlP8yZ"
stripe_account_id = "acct_1GJ14lDCmyQHXl2b"
stripe_card_id = "card_14va654G6L0BSY8tFMU4F8b2"
stripe_charge_id = "ch_14vE3B2eZvKYlo2CcFwpW6cW"

user_ip_address = "172.17.0.1"

captured_charge = stripe.Charge.construct_from(
    {
        "id": stripe_charge_id,
        "captured": True,
        "source": {
            "brand": "Visa",
            "country": "US",
            "customer": stripe_customer_id,
            "exp_month": 12,
            "exp_year": 2016,
            "fingerprint": "i9Tfj0vwzJwrooB7",
            "funding": "credit",
            "id": stripe_card_id,
            "last4": "4242",
            "metadata": {},
            "object": "card",
        },
        "created": 1447454575,
        "currency": "usd",
        "customer": stripe_customer_id,
        "description": "Maven Clinic Billing",
        "amount": 1000,
        "status": "paid",
        "paid": True,
        "refunded": False,
        "refunds": {
            "object": "list",
            "data": [],
            "has_more": False,
            "total_count": 0,
            "url": f"/v1/charges/{stripe_charge_id}/refunds",
        },
    },
    "api_key_foo",
)

zero_card_list = stripe.ListObject.construct_from(
    {"data": [], "url": f"/v1/customers/{stripe_customer_id}/sources"},
    "api_key_foo",
)

customer_no_cards = stripe.Customer.construct_from(
    {"id": stripe_customer_id, "sources": zero_card_list}, "api_key_foo"
)

one_card_list = stripe.ListObject.construct_from(
    {
        "object": "list",
        "url": f"/v1/customers/{stripe_customer_id}/sources",
        "data": [
            {
                "last4": "4242",
                "customer": stripe_customer_id,
                "address_state": None,
                "object": "card",
                "brand": "Visa",
                "address_line1": None,
                "funding": "credit",
                "address_zip_check": None,
                "address_city": None,
                "exp_month": 12,
                "dynamic_last4": None,
                "country": "US",
                "exp_year": 2020,
                "address_line1_check": None,
                "id": stripe_card_id,
                "cvc_check": "pass",
                "address_country": None,
                "name": None,
                "fingerprint": "i9Tfj0vwzJwrooB7",
                "address_line2": None,
                "address_zip": None,
            }
        ],
        "total_count": 1,
        "has_more": False,
    },
    "api_key_foo",
)

customer_one_card = stripe.Customer.construct_from(
    {"id": stripe_customer_id, "sources": one_card_list}, "api_key_foo"
)

uncaptured_payment = stripe.Charge.construct_from(
    {"id": stripe_charge_id, "captured": False, "amount": 5000}, "foo"
)

refunded_charge = stripe.Charge.construct_from(
    {"id": stripe_charge_id, "captured": False, "refunded": True, "amount": 10}, "foo"
)

valid_pharmacy_response = (
    200,
    {
        "Item": {
            "PharmacyId": "1",
            "StoreName": "Test One Pharmacy",
            "Address1": "90001 1ST ST",
            "Address2": "1ST FL",
            "City": "Washington",
            "State": "DC",
            "ZipCode": "20000",
            "PrimaryPhone": "2025551212",
            "PrimaryPhoneType": "Work",
            "PrimaryFax": "2025551213",
            "PharmacySpecialties": [],
        },
        "Result": {"ResultCode": "Result Code 1", "ResultDescription": "Result Code 2"},
    },
)

verified_account = stripe.Account.construct_from(
    {
        "id": "acct_1GJ14lDCmyQHXl2b",
        "object": "account",
        "business_profile": {
            "mcc": None,
            "name": None,
            "product_description": "Maven Wallet Reimbursement Client",
            "support_address": None,
            "support_email": None,
            "support_phone": None,
            "support_url": None,
            "url": None,
        },
        "business_type": "individual",
        "capabilities": {"transfers": "active"},
        "charges_enabled": True,
        "country": "US",
        "created": 1583343128,
        "default_currency": "usd",
        "details_submitted": False,
        "email": None,
        "external_accounts": {
            "data": [
                {
                    "account": "acct_1GIivNJLQWdylfLq",
                    "account_holder_name": "Test Company",
                    "account_holder_type": "company",
                    "bank_name": "STRIPE TEST BANK",
                    "country": "US",
                    "currency": "usd",
                    "default_for_currency": True,
                    "fingerprint": "gS2wpMvong8muvZX",
                    "id": "ba_1Bnq1NBXjxhfe0uu8RYGlIxg",
                    "last4": "6789",
                    "metadata": {},
                    "object": "bank_account",
                    "routing_number": "110000000",
                    "status": "new",
                }
            ],
            "has_more": False,
            "object": "list",
            "total_count": 1,
            "url": "/v1/accounts/acct_1GJ14lDCmyQHXl2b/external_accounts",
            "metadata": {},
            "payouts_enabled": False,
            "requirements": {
                "current_deadline": None,
                "currently_due": [],
                "disabled_reason": None,
                "eventually_due": [],
                "past_due": [],
                "pending_verification": [],
            },
            "settings": {
                "branding": {"icon": None, "logo": None, "primary_color": None},
                "card_payments": {
                    "decline_on": {"avs_failure": False, "cvc_failure": False},
                    "statement_descriptor_prefix": None,
                },
                "dashboard": {"display_name": None, "timezone": "Etc/UTC"},
                "payments": {
                    "statement_descriptor": "",
                    "statement_descriptor_kana": None,
                    "statement_descriptor_kanji": None,
                },
                "payouts": {
                    "debit_negative_balances": False,
                    "schedule": {"delay_days": 2, "interval": "daily"},
                    "statement_descriptor": None,
                },
            },
            "tos_acceptance": {
                "date": 1583273352,
                "ip": "172.17.0.1",
                "user_agent": None,
            },
            "type": "custom",
        },
        "individual": {
            "id": "person_GqiVPH5rdYEOf9",
            "object": "person",
            "account": "acct_1GJ14lDCmyQHXl2b",
            "address": {
                "city": "New York",
                "country": "US",
                "line1": "111 anywhere ave",
                "line2": None,
                "postal_code": "10009",
                "state": "NY",
            },
            "created": 1583343127,
            "dob": {"day": 23, "month": 10, "year": 1977},
            "first_name": "Anybody",
            "id_number_provided": False,
            "last_name": "Person",
            "metadata": {},
            "relationship": {
                "account_opener": True,
                "director": False,
                "executive": False,
                "owner": False,
                "percent_ownership": None,
                "representative": True,
                "title": None,
            },
            "requirements": {
                "currently_due": [],
                "eventually_due": [],
                "past_due": [],
                "pending_verification": [],
            },
            "ssn_last_4_provided": True,
            "verification": {
                "additional_document": {
                    "back": None,
                    "details": None,
                    "details_code": None,
                    "front": None,
                },
                "details": None,
                "details_code": None,
                "document": {
                    "back": None,
                    "details": None,
                    "details_code": None,
                    "front": None,
                },
                "status": "unverified",
            },
        },
        "metadata": {},
        "payouts_enabled": True,
        "requirements": {
            "current_deadline": None,
            "currently_due": [],
            "disabled_reason": None,
            "eventually_due": [],
            "past_due": [],
            "pending_verification": [],
        },
        "tos_acceptance": {"date": 1583343127, "ip": "172.17.0.1", "user_agent": None},
        "type": "custom",
    },
    "api_key_foo",
)

empty_external_accounts = stripe.Account.construct_from(
    {
        "id": "acct_1GJ14lDCmyQHXl2b",
        "object": "account",
        "business_profile": {
            "mcc": None,
            "name": None,
            "product_description": "Maven Wallet Reimbursement Client",
            "support_address": None,
            "support_email": None,
            "support_phone": None,
            "support_url": None,
            "url": None,
        },
        "business_type": "individual",
        "capabilities": {"transfers": "active"},
        "charges_enabled": True,
        "country": "US",
        "created": 1583343128,
        "default_currency": "usd",
        "details_submitted": False,
        "email": None,
        "external_accounts": {
            "object": "list",
            "data": [],
            "has_more": False,
            "total_count": 0,
            "url": "/v1/accounts/acct_1GJ14lDCmyQHXl2b/external_accounts",
        },
        "individual": {
            "id": "person_GqiVPH5rdYEOf9",
            "object": "person",
            "account": "acct_1GJ14lDCmyQHXl2b",
            "address": {
                "city": "New York",
                "country": "US",
                "line1": "111 anywhere ave",
                "line2": None,
                "postal_code": "10009",
                "state": "NY",
            },
            "created": 1583343127,
            "dob": {"day": 23, "month": 10, "year": 1977},
            "first_name": "Anybody",
            "id_number_provided": False,
            "last_name": "Person",
            "metadata": {},
            "relationship": {
                "account_opener": True,
                "director": False,
                "executive": False,
                "owner": False,
                "percent_ownership": None,
                "representative": True,
                "title": None,
            },
            "requirements": {
                "currently_due": [],
                "eventually_due": [],
                "past_due": [],
                "pending_verification": [],
            },
            "ssn_last_4_provided": True,
            "verification": {
                "additional_document": {
                    "back": None,
                    "details": None,
                    "details_code": None,
                    "front": None,
                },
                "details": None,
                "details_code": None,
                "document": {
                    "back": None,
                    "details": None,
                    "details_code": None,
                    "front": None,
                },
                "status": "unverified",
            },
        },
        "metadata": {},
        "payouts_enabled": True,
        "requirements": {
            "current_deadline": None,
            "currently_due": [],
            "disabled_reason": None,
            "eventually_due": [],
            "past_due": [],
            "pending_verification": [],
        },
        "tos_acceptance": {"date": 1583343127, "ip": "172.17.0.1", "user_agent": None},
        "type": "custom",
    },
    "api_key_empty",
)

stripe_business_practitioner_account = stripe.Account.construct_from(
    {
        "id": "acct_1GIivNJLQWdylfLq",
        "object": "account",
        "business_profile": {
            "mcc": None,
            "name": "test",
            "product_description": "Maven Clinic Practitioner",
            "support_address": None,
            "support_email": None,
            "support_phone": None,
            "support_url": None,
            "url": None,
        },
        "business_type": "company",
        "capabilities": {"transfers": "active"},
        "charges_enabled": True,
        "company": {
            "address": {
                "city": "New York",
                "country": "US",
                "line1": "111 anywhere ave",
                "line2": None,
                "postal_code": "10009",
                "state": "NY",
            },
            "directors_provided": False,
            "executives_provided": False,
            "name": "Test Company",
            "owners_provided": False,
            "tax_id_provided": True,
            "verification": {
                "document": {
                    "back": None,
                    "details": None,
                    "details_code": None,
                    "front": None,
                }
            },
        },
        "country": "US",
        "created": 1583273353,
        "default_currency": "usd",
        "details_submitted": False,
        "email": None,
        "external_accounts": {
            "data": [
                {
                    "account": "acct_1GIivNJLQWdylfLq",
                    "account_holder_name": "Test Company",
                    "account_holder_type": "company",
                    "bank_name": "STRIPE TEST BANK",
                    "country": "US",
                    "currency": "usd",
                    "default_for_currency": True,
                    "fingerprint": "gS2wpMvong8muvZX",
                    "id": "ba_1Bnq1NBXjxhfe0uu8RYGlIxg",
                    "last4": "6789",
                    "metadata": {},
                    "object": "bank_account",
                    "routing_number": "110000000",
                    "status": "new",
                }
            ],
            "has_more": False,
            "object": "list",
            "total_count": 1,
            "url": "/v1/accounts/acct_1GIivNJLQWdylfLq/external_accounts",
            "metadata": {},
            "payouts_enabled": False,
            "requirements": {
                "current_deadline": None,
                "currently_due": [],
                "disabled_reason": None,
                "eventually_due": [],
                "past_due": [],
                "pending_verification": [],
            },
            "settings": {
                "branding": {"icon": None, "logo": None, "primary_color": None},
                "card_payments": {
                    "decline_on": {"avs_failure": False, "cvc_failure": False},
                    "statement_descriptor_prefix": None,
                },
                "dashboard": {"display_name": None, "timezone": "Etc/UTC"},
                "payments": {
                    "statement_descriptor": "",
                    "statement_descriptor_kana": None,
                    "statement_descriptor_kanji": None,
                },
                "payouts": {
                    "debit_negative_balances": False,
                    "schedule": {"delay_days": 2, "interval": "daily"},
                    "statement_descriptor": None,
                },
            },
            "type": "custom",
        },
        "tos_acceptance": {
            "date": 1583273352,
            "ip": "172.17.0.1",
            "user_agent": None,
        },
    },
    "api_key_foo",
)


def fail_charge_capture(amount):
    raise stripe.error.StripeError(code="charge_expired_for_capture")
