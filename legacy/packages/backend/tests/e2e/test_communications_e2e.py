"""
E2E CRUD Tests for TaxasGE Communications Module
Tests email templates, SMS templates, webhooks, USSD configurations,
notification templates, and push templates.

Run with: python -m pytest tests/e2e/test_communications_e2e.py -v -s
Or directly: python tests/e2e/test_communications_e2e.py

NOTE: Run after deployment when database tables exist and backend is running.
"""

import requests
import json
from datetime import datetime
import sys

# Configuration
API_URL = "https://taxasge-backend-staging-xrlbgdr5eq-uc.a.run.app"
# API_URL = "http://localhost:8000"  # For local testing

# Test data storage
created_ids = {
    "email_template_id": None,
    "sms_template_id": None,
    "webhook_id": None,
    "ussd_config_id": None,
    "notification_template_id": None,
    "push_template_id": None,
}

# Test results
results = {
    "passed": 0,
    "failed": 0,
    "errors": []
}


def log_test(name: str, success: bool, message: str = ""):
    """Log test result"""
    status = "✅ PASSED" if success else "❌ FAILED"
    print(f"\n{status}: {name}")
    if message:
        print(f"   {message}")
    if success:
        results["passed"] += 1
    else:
        results["failed"] += 1
        results["errors"].append(f"{name}: {message}")


def get_auth_token():
    """Get authentication token - try multiple credentials"""
    credentials = [
        {"email": "kouemou.sah@gmail.com", "password": "Admin123!"},
        {"email": "admin@taxasge.gq", "password": "Admin123!"},
        {"email": "test@taxasge.gq", "password": "Test123!"},
    ]

    for cred in credentials:
        try:
            response = requests.post(
                f"{API_URL}/api/v1/auth/login",
                json=cred,
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token") or data.get("token")
                if token:
                    print(f"✅ Authenticated with {cred['email']}")
                    return token
        except Exception as e:
            continue

    return None


def make_request(method: str, endpoint: str, token: str = None, data: dict = None):
    """Make API request with proper headers"""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"{API_URL}{endpoint}"

    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=30)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=data, timeout=30)
        elif method == "PATCH":
            response = requests.patch(url, headers=headers, json=data, timeout=30)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, timeout=30)
        else:
            raise ValueError(f"Unknown method: {method}")

        return response
    except requests.exceptions.RequestException as e:
        print(f"   Request error: {e}")
        return None


# ============================================================================
# TEST 1: Email Templates CRUD
# ============================================================================
def test_create_email_template(token: str):
    """Create an email template"""
    timestamp = datetime.now().strftime("%H%M%S")
    data = {
        "templateCode": f"EMAIL_TEST_{timestamp}",
        "nameEs": f"Plantilla Email de Prueba {timestamp}",
        "nameFr": f"Modèle Email de Test {timestamp}",
        "nameEn": f"Test Email Template {timestamp}",
        "subjectEs": "Asunto de prueba E2E",
        "subjectFr": "Sujet de test E2E",
        "subjectEn": "E2E Test Subject",
        "descriptionEs": "Descripción de la plantilla de correo para pruebas E2E",
        "htmlContent": "<html><body><h1>{{user_name}}</h1><p>Contenido de prueba</p></body></html>",
        "variables": [
            {"name": "user_name", "description": "Nombre del usuario", "required": True},
            {"name": "amount", "description": "Monto", "example": "50000 XAF", "required": False}
        ],
        "category": "test",
        "isActive": True
    }

    response = make_request("POST", "/api/v1/admin/communications/email-templates", token, data)

    if response and response.status_code in [200, 201]:
        result = response.json()
        created_ids["email_template_id"] = result.get("id")
        log_test("CREATE Email Template", True, f"ID: {created_ids['email_template_id']}")
        return True
    else:
        status = response.status_code if response else "No response"
        body = response.text if response else "N/A"
        log_test("CREATE Email Template", False, f"Status: {status}, Body: {body[:300]}")
        return False


def test_read_email_template(token: str):
    """Read the created email template"""
    template_id = created_ids["email_template_id"]
    if not template_id:
        log_test("READ Email Template", False, "No template ID available")
        return False

    response = make_request("GET", f"/api/v1/admin/communications/email-templates/{template_id}", token)

    if response and response.status_code == 200:
        log_test("READ Email Template", True, f"ID: {template_id}")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("READ Email Template", False, f"Status: {status}")
        return False


def test_update_email_template(token: str):
    """Update the created email template"""
    template_id = created_ids["email_template_id"]
    if not template_id:
        log_test("UPDATE Email Template", False, "No template ID available")
        return False

    data = {
        "nameEs": "Plantilla Email Actualizada",
        "subjectEs": "Asunto actualizado E2E",
        "isActive": True
    }

    response = make_request("PUT", f"/api/v1/admin/communications/email-templates/{template_id}", token, data)

    if response and response.status_code in [200, 204]:
        log_test("UPDATE Email Template", True, f"ID: {template_id}")
        return True
    else:
        status = response.status_code if response else "No response"
        body = response.text if response else "N/A"
        log_test("UPDATE Email Template", False, f"Status: {status}, Body: {body[:200]}")
        return False


def test_list_email_templates(token: str):
    """List all email templates"""
    response = make_request("GET", "/api/v1/admin/communications/email-templates", token)

    if response and response.status_code == 200:
        data = response.json()
        total = data.get("total", len(data.get("templates", [])))
        log_test("LIST Email Templates", True, f"Total: {total} templates")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("LIST Email Templates", False, f"Status: {status}")
        return False


# ============================================================================
# TEST 2: SMS Templates CRUD
# ============================================================================
def test_create_sms_template(token: str):
    """Create an SMS template"""
    timestamp = datetime.now().strftime("%H%M%S")
    data = {
        "templateCode": f"SMS_TEST_{timestamp}",
        "nameEs": f"Plantilla SMS de Prueba {timestamp}",
        "nameFr": f"Modèle SMS de Test {timestamp}",
        "nameEn": f"Test SMS Template {timestamp}",
        "contentEs": "Hola {{user_name}}, su pago de {{amount}} XAF ha sido recibido. Ref: {{ref_id}}",
        "contentFr": "Bonjour {{user_name}}, votre paiement de {{amount}} XAF a été reçu. Réf: {{ref_id}}",
        "contentEn": "Hello {{user_name}}, your payment of {{amount}} XAF has been received. Ref: {{ref_id}}",
        "variables": ["user_name", "amount", "ref_id"],
        "category": "payments",
        "maxSegments": 2,
        "isActive": True
    }

    response = make_request("POST", "/api/v1/admin/communications/sms-templates", token, data)

    if response and response.status_code in [200, 201]:
        result = response.json()
        created_ids["sms_template_id"] = result.get("id")
        log_test("CREATE SMS Template", True, f"ID: {created_ids['sms_template_id']}")
        return True
    else:
        status = response.status_code if response else "No response"
        body = response.text if response else "N/A"
        log_test("CREATE SMS Template", False, f"Status: {status}, Body: {body[:300]}")
        return False


def test_read_sms_template(token: str):
    """Read the created SMS template"""
    template_id = created_ids["sms_template_id"]
    if not template_id:
        log_test("READ SMS Template", False, "No template ID available")
        return False

    response = make_request("GET", f"/api/v1/admin/communications/sms-templates/{template_id}", token)

    if response and response.status_code == 200:
        log_test("READ SMS Template", True, f"ID: {template_id}")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("READ SMS Template", False, f"Status: {status}")
        return False


def test_update_sms_template(token: str):
    """Update the created SMS template"""
    template_id = created_ids["sms_template_id"]
    if not template_id:
        log_test("UPDATE SMS Template", False, "No template ID available")
        return False

    data = {
        "nameEs": "Plantilla SMS Actualizada",
        "contentEs": "Mensaje SMS actualizado: {{user_name}}, ref: {{ref_id}}",
        "maxSegments": 1
    }

    response = make_request("PUT", f"/api/v1/admin/communications/sms-templates/{template_id}", token, data)

    if response and response.status_code in [200, 204]:
        log_test("UPDATE SMS Template", True, f"ID: {template_id}")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("UPDATE SMS Template", False, f"Status: {status}")
        return False


def test_list_sms_templates(token: str):
    """List all SMS templates"""
    response = make_request("GET", "/api/v1/admin/communications/sms-templates", token)

    if response and response.status_code == 200:
        data = response.json()
        total = data.get("total", len(data.get("templates", [])))
        log_test("LIST SMS Templates", True, f"Total: {total} templates")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("LIST SMS Templates", False, f"Status: {status}")
        return False


# ============================================================================
# TEST 3: Webhook Configurations CRUD
# ============================================================================
def test_create_webhook(token: str):
    """Create a webhook configuration"""
    timestamp = datetime.now().strftime("%H%M%S")
    data = {
        "name": f"Webhook de Prueba {timestamp}",
        "webhookType": "custom",
        "endpointUrl": "https://webhook.site/test-endpoint",
        "httpMethod": "POST",
        "headers": {"X-Custom-Header": "test-value"},
        "authType": "bearer",
        "authConfig": {"token": "test-bearer-token"},
        "payloadTemplate": {"event": "{{event_type}}", "data": "{{payload}}"},
        "retryConfig": {"max_retries": 3, "retry_delay_seconds": 60},
        "timeoutSeconds": 30,
        "events": ["payment.completed", "declaration.submitted"],
        "isActive": True
    }

    response = make_request("POST", "/api/v1/admin/communications/webhooks", token, data)

    if response and response.status_code in [200, 201]:
        result = response.json()
        created_ids["webhook_id"] = result.get("id")
        log_test("CREATE Webhook", True, f"ID: {created_ids['webhook_id']}")
        return True
    else:
        status = response.status_code if response else "No response"
        body = response.text if response else "N/A"
        log_test("CREATE Webhook", False, f"Status: {status}, Body: {body[:300]}")
        return False


def test_read_webhook(token: str):
    """Read the created webhook"""
    webhook_id = created_ids["webhook_id"]
    if not webhook_id:
        log_test("READ Webhook", False, "No webhook ID available")
        return False

    response = make_request("GET", f"/api/v1/admin/communications/webhooks/{webhook_id}", token)

    if response and response.status_code == 200:
        log_test("READ Webhook", True, f"ID: {webhook_id}")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("READ Webhook", False, f"Status: {status}")
        return False


def test_update_webhook(token: str):
    """Update the created webhook"""
    webhook_id = created_ids["webhook_id"]
    if not webhook_id:
        log_test("UPDATE Webhook", False, "No webhook ID available")
        return False

    data = {
        "name": "Webhook Actualizado",
        "timeoutSeconds": 60,
        "isActive": False
    }

    response = make_request("PUT", f"/api/v1/admin/communications/webhooks/{webhook_id}", token, data)

    if response and response.status_code in [200, 204]:
        log_test("UPDATE Webhook", True, f"ID: {webhook_id}")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("UPDATE Webhook", False, f"Status: {status}")
        return False


def test_list_webhooks(token: str):
    """List all webhooks"""
    response = make_request("GET", "/api/v1/admin/communications/webhooks", token)

    if response and response.status_code == 200:
        data = response.json()
        total = data.get("total", len(data.get("webhooks", [])))
        log_test("LIST Webhooks", True, f"Total: {total} webhooks")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("LIST Webhooks", False, f"Status: {status}")
        return False


# ============================================================================
# TEST 4: USSD Configurations CRUD
# ============================================================================
def test_create_ussd_config(token: str):
    """Create a USSD configuration"""
    timestamp = datetime.now().strftime("%H%M%S")
    data = {
        "operatorName": "getesa",
        "operatorCode": f"GETESA_TEST_{timestamp}",
        "shortCode": f"*123#",
        "apiEndpoint": "https://api.getesa.gq/ussd",
        "authConfig": {"apiKey": "test-api-key"},
        "menuStructure": [
            {
                "id": "main",
                "titleEs": "Bienvenido a TaxasGE",
                "titleFr": "Bienvenue à TaxasGE",
                "titleEn": "Welcome to TaxasGE",
                "isRoot": True,
                "options": [
                    {"key": "1", "labelEs": "Consultar Saldo", "labelFr": "Consulter Solde", "action": "balance"},
                    {"key": "2", "labelEs": "Información Fiscal", "labelFr": "Info Fiscale", "action": "tax_info"},
                    {"key": "3", "labelEs": "Soporte", "labelFr": "Support", "nextMenu": "support"}
                ]
            },
            {
                "id": "support",
                "titleEs": "Soporte Técnico",
                "titleFr": "Support Technique",
                "isRoot": False,
                "parentMenu": "main",
                "options": [
                    {"key": "1", "labelEs": "Llamar Soporte", "action": "support"},
                    {"key": "0", "labelEs": "Volver", "nextMenu": "main"}
                ]
            }
        ],
        "sessionTimeoutSeconds": 180,
        "maxInputLength": 160,
        "isActive": True
    }

    response = make_request("POST", "/api/v1/admin/communications/ussd", token, data)

    if response and response.status_code in [200, 201]:
        result = response.json()
        created_ids["ussd_config_id"] = result.get("id")
        log_test("CREATE USSD Config", True, f"ID: {created_ids['ussd_config_id']}")
        return True
    else:
        status = response.status_code if response else "No response"
        body = response.text if response else "N/A"
        log_test("CREATE USSD Config", False, f"Status: {status}, Body: {body[:300]}")
        return False


def test_read_ussd_config(token: str):
    """Read the created USSD config"""
    config_id = created_ids["ussd_config_id"]
    if not config_id:
        log_test("READ USSD Config", False, "No config ID available")
        return False

    response = make_request("GET", f"/api/v1/admin/communications/ussd/{config_id}", token)

    if response and response.status_code == 200:
        log_test("READ USSD Config", True, f"ID: {config_id}")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("READ USSD Config", False, f"Status: {status}")
        return False


def test_update_ussd_config(token: str):
    """Update the created USSD config"""
    config_id = created_ids["ussd_config_id"]
    if not config_id:
        log_test("UPDATE USSD Config", False, "No config ID available")
        return False

    data = {
        "sessionTimeoutSeconds": 300,
        "isActive": False
    }

    response = make_request("PUT", f"/api/v1/admin/communications/ussd/{config_id}", token, data)

    if response and response.status_code in [200, 204]:
        log_test("UPDATE USSD Config", True, f"ID: {config_id}")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("UPDATE USSD Config", False, f"Status: {status}")
        return False


def test_list_ussd_configs(token: str):
    """List all USSD configurations"""
    response = make_request("GET", "/api/v1/admin/communications/ussd", token)

    if response and response.status_code == 200:
        data = response.json()
        total = data.get("total", len(data.get("configs", [])))
        log_test("LIST USSD Configs", True, f"Total: {total} configs")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("LIST USSD Configs", False, f"Status: {status}")
        return False


# ============================================================================
# TEST 5: Notification Templates CRUD
# ============================================================================
def test_create_notification_template(token: str):
    """Create a notification template"""
    timestamp = datetime.now().strftime("%H%M%S")
    data = {
        "templateCode": f"NOTIF_TEST_{timestamp}",
        "nameEs": f"Plantilla Notificación de Prueba {timestamp}",
        "nameFr": f"Modèle Notification de Test {timestamp}",
        "nameEn": f"Test Notification Template {timestamp}",
        "titleEs": "Pago Recibido",
        "titleFr": "Paiement Reçu",
        "titleEn": "Payment Received",
        "bodyEs": "Su pago de {{amount}} XAF ha sido procesado exitosamente.",
        "bodyFr": "Votre paiement de {{amount}} XAF a été traité avec succès.",
        "bodyEn": "Your payment of {{amount}} XAF has been processed successfully.",
        "icon": "check-circle",
        "actionUrl": "/dashboard/payments",
        "variables": ["amount", "payment_id"],
        "notificationType": "success",
        "priority": "normal",
        "isActive": True
    }

    response = make_request("POST", "/api/v1/admin/communications/notification-templates", token, data)

    if response and response.status_code in [200, 201]:
        result = response.json()
        created_ids["notification_template_id"] = result.get("id")
        log_test("CREATE Notification Template", True, f"ID: {created_ids['notification_template_id']}")
        return True
    else:
        status = response.status_code if response else "No response"
        body = response.text if response else "N/A"
        log_test("CREATE Notification Template", False, f"Status: {status}, Body: {body[:300]}")
        return False


def test_read_notification_template(token: str):
    """Read the created notification template"""
    template_id = created_ids["notification_template_id"]
    if not template_id:
        log_test("READ Notification Template", False, "No template ID available")
        return False

    response = make_request("GET", f"/api/v1/admin/communications/notification-templates/{template_id}", token)

    if response and response.status_code == 200:
        log_test("READ Notification Template", True, f"ID: {template_id}")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("READ Notification Template", False, f"Status: {status}")
        return False


def test_update_notification_template(token: str):
    """Update the created notification template"""
    template_id = created_ids["notification_template_id"]
    if not template_id:
        log_test("UPDATE Notification Template", False, "No template ID available")
        return False

    data = {
        "titleEs": "Pago Confirmado",
        "priority": "high",
        "isActive": True
    }

    response = make_request("PUT", f"/api/v1/admin/communications/notification-templates/{template_id}", token, data)

    if response and response.status_code in [200, 204]:
        log_test("UPDATE Notification Template", True, f"ID: {template_id}")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("UPDATE Notification Template", False, f"Status: {status}")
        return False


def test_list_notification_templates(token: str):
    """List all notification templates"""
    response = make_request("GET", "/api/v1/admin/communications/notification-templates", token)

    if response and response.status_code == 200:
        data = response.json()
        total = data.get("total", len(data.get("templates", [])))
        log_test("LIST Notification Templates", True, f"Total: {total} templates")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("LIST Notification Templates", False, f"Status: {status}")
        return False


# ============================================================================
# TEST 6: Push Templates CRUD
# ============================================================================
def test_create_push_template(token: str):
    """Create a push notification template"""
    timestamp = datetime.now().strftime("%H%M%S")
    data = {
        "templateCode": f"PUSH_TEST_{timestamp}",
        "nameEs": f"Plantilla Push de Prueba {timestamp}",
        "nameFr": f"Modèle Push de Test {timestamp}",
        "nameEn": f"Test Push Template {timestamp}",
        "titleEs": "Nueva Declaración",
        "titleFr": "Nouvelle Déclaration",
        "titleEn": "New Declaration",
        "bodyEs": "Su declaración {{declaration_type}} está lista para revisión.",
        "bodyFr": "Votre déclaration {{declaration_type}} est prête pour révision.",
        "bodyEn": "Your {{declaration_type}} declaration is ready for review.",
        "imageUrl": "https://taxasge.gq/images/notification.png",
        "iconUrl": "https://taxasge.gq/icons/declaration.png",
        "clickAction": "/dashboard/declarations",
        "dataPayload": {"type": "declaration", "priority": "high"},
        "variables": ["declaration_type", "declaration_id"],
        "platform": "all",
        "ttlSeconds": 86400,
        "isActive": True
    }

    response = make_request("POST", "/api/v1/admin/communications/push-templates", token, data)

    if response and response.status_code in [200, 201]:
        result = response.json()
        created_ids["push_template_id"] = result.get("id")
        log_test("CREATE Push Template", True, f"ID: {created_ids['push_template_id']}")
        return True
    else:
        status = response.status_code if response else "No response"
        body = response.text if response else "N/A"
        log_test("CREATE Push Template", False, f"Status: {status}, Body: {body[:300]}")
        return False


def test_read_push_template(token: str):
    """Read the created push template"""
    template_id = created_ids["push_template_id"]
    if not template_id:
        log_test("READ Push Template", False, "No template ID available")
        return False

    response = make_request("GET", f"/api/v1/admin/communications/push-templates/{template_id}", token)

    if response and response.status_code == 200:
        log_test("READ Push Template", True, f"ID: {template_id}")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("READ Push Template", False, f"Status: {status}")
        return False


def test_update_push_template(token: str):
    """Update the created push template"""
    template_id = created_ids["push_template_id"]
    if not template_id:
        log_test("UPDATE Push Template", False, "No template ID available")
        return False

    data = {
        "titleEs": "Declaración Lista",
        "platform": "android",
        "ttlSeconds": 172800
    }

    response = make_request("PUT", f"/api/v1/admin/communications/push-templates/{template_id}", token, data)

    if response and response.status_code in [200, 204]:
        log_test("UPDATE Push Template", True, f"ID: {template_id}")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("UPDATE Push Template", False, f"Status: {status}")
        return False


def test_list_push_templates(token: str):
    """List all push templates"""
    response = make_request("GET", "/api/v1/admin/communications/push-templates", token)

    if response and response.status_code == 200:
        data = response.json()
        total = data.get("total", len(data.get("templates", [])))
        log_test("LIST Push Templates", True, f"Total: {total} templates")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("LIST Push Templates", False, f"Status: {status}")
        return False


# ============================================================================
# DELETE TESTS - Cleanup
# ============================================================================
def test_delete_email_template(token: str):
    """Delete the created email template"""
    template_id = created_ids["email_template_id"]
    if not template_id:
        log_test("DELETE Email Template", False, "No template ID available")
        return False

    response = make_request("DELETE", f"/api/v1/admin/communications/email-templates/{template_id}", token)

    if response and response.status_code in [200, 204]:
        log_test("DELETE Email Template", True, f"ID: {template_id}")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("DELETE Email Template", False, f"Status: {status}")
        return False


def test_delete_sms_template(token: str):
    """Delete the created SMS template"""
    template_id = created_ids["sms_template_id"]
    if not template_id:
        log_test("DELETE SMS Template", False, "No template ID available")
        return False

    response = make_request("DELETE", f"/api/v1/admin/communications/sms-templates/{template_id}", token)

    if response and response.status_code in [200, 204]:
        log_test("DELETE SMS Template", True, f"ID: {template_id}")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("DELETE SMS Template", False, f"Status: {status}")
        return False


def test_delete_webhook(token: str):
    """Delete the created webhook"""
    webhook_id = created_ids["webhook_id"]
    if not webhook_id:
        log_test("DELETE Webhook", False, "No webhook ID available")
        return False

    response = make_request("DELETE", f"/api/v1/admin/communications/webhooks/{webhook_id}", token)

    if response and response.status_code in [200, 204]:
        log_test("DELETE Webhook", True, f"ID: {webhook_id}")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("DELETE Webhook", False, f"Status: {status}")
        return False


def test_delete_ussd_config(token: str):
    """Delete the created USSD config"""
    config_id = created_ids["ussd_config_id"]
    if not config_id:
        log_test("DELETE USSD Config", False, "No config ID available")
        return False

    response = make_request("DELETE", f"/api/v1/admin/communications/ussd/{config_id}", token)

    if response and response.status_code in [200, 204]:
        log_test("DELETE USSD Config", True, f"ID: {config_id}")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("DELETE USSD Config", False, f"Status: {status}")
        return False


def test_delete_notification_template(token: str):
    """Delete the created notification template"""
    template_id = created_ids["notification_template_id"]
    if not template_id:
        log_test("DELETE Notification Template", False, "No template ID available")
        return False

    response = make_request("DELETE", f"/api/v1/admin/communications/notification-templates/{template_id}", token)

    if response and response.status_code in [200, 204]:
        log_test("DELETE Notification Template", True, f"ID: {template_id}")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("DELETE Notification Template", False, f"Status: {status}")
        return False


def test_delete_push_template(token: str):
    """Delete the created push template"""
    template_id = created_ids["push_template_id"]
    if not template_id:
        log_test("DELETE Push Template", False, "No template ID available")
        return False

    response = make_request("DELETE", f"/api/v1/admin/communications/push-templates/{template_id}", token)

    if response and response.status_code in [200, 204]:
        log_test("DELETE Push Template", True, f"ID: {template_id}")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("DELETE Push Template", False, f"Status: {status}")
        return False


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================
def run_tests():
    """Run all E2E tests for Communications module"""
    print("=" * 60)
    print("TaxasGE Communications Module E2E Tests")
    print(f"API: {API_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Authenticate
    print("\n🔐 Authenticating...")
    token = get_auth_token()

    if not token:
        print("❌ CRITICAL: Could not authenticate. Tests will run without auth.")
        print("   Some tests may fail due to missing permissions.")
        token = None

    # Run Email Template tests
    print("\n" + "=" * 60)
    print("PHASE 1: EMAIL TEMPLATES CRUD")
    print("=" * 60)
    test_create_email_template(token)
    test_read_email_template(token)
    test_update_email_template(token)
    test_list_email_templates(token)

    # Run SMS Template tests
    print("\n" + "=" * 60)
    print("PHASE 2: SMS TEMPLATES CRUD")
    print("=" * 60)
    test_create_sms_template(token)
    test_read_sms_template(token)
    test_update_sms_template(token)
    test_list_sms_templates(token)

    # Run Webhook tests
    print("\n" + "=" * 60)
    print("PHASE 3: WEBHOOKS CRUD")
    print("=" * 60)
    test_create_webhook(token)
    test_read_webhook(token)
    test_update_webhook(token)
    test_list_webhooks(token)

    # Run USSD Config tests
    print("\n" + "=" * 60)
    print("PHASE 4: USSD CONFIGURATIONS CRUD")
    print("=" * 60)
    test_create_ussd_config(token)
    test_read_ussd_config(token)
    test_update_ussd_config(token)
    test_list_ussd_configs(token)

    # Run Notification Template tests
    print("\n" + "=" * 60)
    print("PHASE 5: NOTIFICATION TEMPLATES CRUD")
    print("=" * 60)
    test_create_notification_template(token)
    test_read_notification_template(token)
    test_update_notification_template(token)
    test_list_notification_templates(token)

    # Run Push Template tests
    print("\n" + "=" * 60)
    print("PHASE 6: PUSH TEMPLATES CRUD")
    print("=" * 60)
    test_create_push_template(token)
    test_read_push_template(token)
    test_update_push_template(token)
    test_list_push_templates(token)

    # Cleanup - Delete all created resources
    print("\n" + "=" * 60)
    print("PHASE 7: CLEANUP (DELETE OPERATIONS)")
    print("=" * 60)
    test_delete_email_template(token)
    test_delete_sms_template(token)
    test_delete_webhook(token)
    test_delete_ussd_config(token)
    test_delete_notification_template(token)
    test_delete_push_template(token)

    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"Total: {results['passed'] + results['failed']}")

    if results["errors"]:
        print("\n⚠️  Errors:")
        for error in results["errors"]:
            print(f"   - {error}")

    print("\n📋 Created Resource IDs (before cleanup):")
    for key, value in created_ids.items():
        print(f"   {key}: {value}")

    return results["failed"] == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
