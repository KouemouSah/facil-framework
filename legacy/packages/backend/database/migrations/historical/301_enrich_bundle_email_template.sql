-- Migration 301: Add {{bundle_section}} to payment_cash_validated email template
--
-- B7: Bundle email enrichment — when a bundle split is validated, the email
-- now includes entity name, progress (X/N), and obligation names.
-- For non-bundle payments, {{bundle_section}} is empty and gets cleaned
-- by the regex in notification_handler._render_template (line 810).
--
-- Idempotent: only updates if bundle_section is not already present.

UPDATE email_templates
SET html_content = REPLACE(
    html_content,
    '{{receipt_number}}</td>
                    </tr>',
    '{{receipt_number}}</td>
                    </tr>
                    {{bundle_section}}'
)
WHERE template_code = 'payment_cash_validated'
  AND html_content NOT LIKE '%bundle_section%';
