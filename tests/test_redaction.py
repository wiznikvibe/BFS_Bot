from bfs_bot.redaction import RedactionReport, redact_customer_record


def test_redacts_customer_pii_with_stable_placeholders():
    customer = {
        "customer_id": "SME-10023",
        "business_name": "Mehta Packaging LLP",
        "contact_name": "Riya Mehta",
        "email": "riya.mehta@example.com",
        "phone": "+91 98765 43210",
        "pan": "ABCDE1234F",
        "gstin": "27ABCDE1234F1Z5",
        "registered_address": "42 MG Road, Pune",
        "credit_limit": 250000,
    }

    redacted, report = redact_customer_record(customer)

    assert redacted["customer_id"] == "SME-10023"
    assert redacted["business_name"] == "[BUSINESS_NAME]"
    assert redacted["contact_name"] == "[CONTACT_NAME]"
    assert redacted["email"] == "[EMAIL]"
    assert redacted["phone"] == "[PHONE]"
    assert redacted["pan"] == "[PAN]"
    assert redacted["gstin"] == "[GSTIN]"
    assert redacted["registered_address"] == "[ADDRESS]"
    assert redacted["credit_limit"] == 250000
    assert isinstance(report, RedactionReport)
    assert report.status == "passed"
    assert set(report.redacted_fields) >= {
        "business_name",
        "contact_name",
        "email",
        "phone",
        "pan",
        "gstin",
        "registered_address",
    }


def test_report_flags_unredacted_pii_patterns():
    redacted, report = redact_customer_record(
        {
            "customer_id": "SME-10024",
            "notes": "Call +91 99887 77665 or email owner@example.com",
        }
    )

    assert redacted["notes"] == "Call [PHONE] or email [EMAIL]"
    assert report.status == "passed"
    assert report.pattern_replacements["phone"] == 1
    assert report.pattern_replacements["email"] == 1
