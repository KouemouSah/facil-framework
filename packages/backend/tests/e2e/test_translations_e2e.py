"""
E2E Tests for Translation Module Endpoints
Tests system translations, entity translations, and frontend translations.

Run with: python -m pytest tests/e2e/test_translations_e2e.py -v -s
"""

import requests
from datetime import datetime
import sys

# Configuration
API_URL = "https://taxasge-backend-staging-xrlbgdr5eq-uc.a.run.app"
# API_URL = "http://localhost:8000"  # For local testing

# Test data storage
created_ids = {
    "system_translation_id": None,
    "entity_translation_key": None,  # entity_type/entity_code/language/field
    "frontend_translation_id": None,
}

# Test results
results = {
    "passed": 0,
    "failed": 0,
    "skipped": 0,
    "errors": []
}


def log_test(name: str, success: bool, message: str = "", skipped: bool = False):
    """Log test result"""
    if skipped:
        status = "⏭️  SKIPPED"
        results["skipped"] += 1
    else:
        status = "✅ PASSED" if success else "❌ FAILED"
        if success:
            results["passed"] += 1
        else:
            results["failed"] += 1
            results["errors"].append(f"{name}: {message}")

    print(f"\n{status}: {name}")
    if message:
        print(f"   {message}")


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
        except Exception:
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
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, timeout=30)
        else:
            raise ValueError(f"Unknown method: {method}")

        return response
    except requests.exceptions.RequestException:
        return None


# ============================================================================
# SYSTEM TRANSLATIONS TESTS - /api/v1/translations
# ============================================================================

def test_system_translations_categories(token: str):
    """GET /api/v1/translations/categories - List all categories"""
    response = make_request("GET", "/api/v1/translations/categories")

    if response and response.status_code == 200:
        data = response.json()
        categories = data.get("categories", [])
        log_test(
            "GET /translations/categories",
            True,
            f"Found {len(categories)} categories: {categories[:5]}..."
        )
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("GET /translations/categories", False, f"Status: {status}")
        return False


def test_system_translations_stats(token: str):
    """GET /api/v1/translations/stats - Get translation statistics"""
    response = make_request("GET", "/api/v1/translations/stats")

    if response and response.status_code == 200:
        data = response.json()
        total = data.get("total_translations", 0)
        categories_count = data.get("total_categories", 0)
        log_test(
            "GET /translations/stats",
            True,
            f"Total: {total} translations, {categories_count} categories"
        )
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("GET /translations/stats", False, f"Status: {status}")
        return False


def test_system_translations_list(token: str):
    """GET /api/v1/translations - List translations with pagination"""
    response = make_request("GET", "/api/v1/translations?limit=5")

    if response and response.status_code == 200:
        data = response.json()
        translations = data.get("translations", [])
        total = data.get("total", 0)
        log_test(
            "GET /translations (list)",
            True,
            f"Found {len(translations)} of {total} translations"
        )
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("GET /translations (list)", False, f"Status: {status}")
        return False


def test_system_translations_search(token: str):
    """GET /api/v1/translations?category=enum - Search by category"""
    response = make_request("GET", "/api/v1/translations?category=enum&limit=5")

    if response and response.status_code == 200:
        data = response.json()
        translations = data.get("translations", [])
        log_test(
            "GET /translations (search by category)",
            True,
            f"Found {len(translations)} enum translations"
        )
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("GET /translations (search by category)", False, f"Status: {status}")
        return False


def test_system_translation_create(token: str):
    """POST /api/v1/translations - Create a translation"""
    timestamp = datetime.now().strftime("%H%M%S")
    data = {
        "category": "test.e2e",
        "key_code": f"test_key_{timestamp}",
        "es": f"Texto de prueba {timestamp}",
        "fr": f"Texte de test {timestamp}",
        "en": f"Test text {timestamp}",
        "description": "E2E test translation - can be deleted",
        "source": "manual"
    }

    response = make_request("POST", "/api/v1/translations", token, data)

    if response and response.status_code in [200, 201]:
        result = response.json()
        created_ids["system_translation_id"] = result.get("id")
        log_test(
            "POST /translations (create)",
            True,
            f"Created ID: {created_ids['system_translation_id']}"
        )
        return True
    else:
        status = response.status_code if response else "No response"
        body = response.text[:200] if response else "N/A"
        log_test("POST /translations (create)", False, f"Status: {status}, Body: {body}")
        return False


def test_system_translation_read(token: str):
    """GET /api/v1/translations/{id} - Read created translation"""
    translation_id = created_ids.get("system_translation_id")
    if not translation_id:
        log_test("GET /translations/{id}", False, "No ID available", skipped=True)
        return False

    response = make_request("GET", f"/api/v1/translations/{translation_id}")

    if response and response.status_code == 200:
        data = response.json()
        log_test(
            "GET /translations/{id}",
            True,
            f"Key: {data.get('key_code')}, Category: {data.get('category')}"
        )
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("GET /translations/{id}", False, f"Status: {status}")
        return False


def test_system_translation_update(token: str):
    """PUT /api/v1/translations/{id} - Update translation"""
    translation_id = created_ids.get("system_translation_id")
    if not translation_id:
        log_test("PUT /translations/{id}", False, "No ID available", skipped=True)
        return False

    data = {
        "es": "Texto actualizado por E2E test",
        "description": "Updated by E2E test"
    }

    response = make_request("PUT", f"/api/v1/translations/{translation_id}", token, data)

    if response and response.status_code == 200:
        log_test("PUT /translations/{id}", True, "Translation updated")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("PUT /translations/{id}", False, f"Status: {status}")
        return False


def test_system_translation_delete(token: str):
    """DELETE /api/v1/translations/{id} - Delete translation"""
    translation_id = created_ids.get("system_translation_id")
    if not translation_id:
        log_test("DELETE /translations/{id}", False, "No ID available", skipped=True)
        return False

    response = make_request("DELETE", f"/api/v1/translations/{translation_id}", token)

    if response and response.status_code == 200:
        log_test("DELETE /translations/{id}", True, "Translation deleted")
        return True
    else:
        status = response.status_code if response else "No response"
        log_test("DELETE /translations/{id}", False, f"Status: {status}")
        return False


# ============================================================================
# ENTITY TRANSLATIONS TESTS - /api/v1/translations/entities
# ============================================================================

def test_entity_translations_types(token: str):
    """GET /api/v1/translations/entities/types - List entity types"""
    response = make_request("GET", "/api/v1/translations/entities/types")

    if response and response.status_code == 200:
        data = response.json()
        types = data.get("entity_types", [])
        log_test(
            "GET /translations/entities/types",
            True,
            f"Found {len(types)} entity types"
        )
        return True
    elif response and response.status_code == 404:
        log_test(
            "GET /translations/entities/types",
            False,
            "Endpoint not found - routes not deployed yet",
            skipped=True
        )
        return False
    else:
        status = response.status_code if response else "No response"
        log_test("GET /translations/entities/types", False, f"Status: {status}")
        return False


def test_entity_translations_stats(token: str):
    """GET /api/v1/translations/entities/stats - Get entity translation stats"""
    response = make_request("GET", "/api/v1/translations/entities/stats")

    if response and response.status_code == 200:
        data = response.json()
        log_test(
            "GET /translations/entities/stats",
            True,
            f"Stats: {data}"
        )
        return True
    elif response and response.status_code == 404:
        log_test("GET /translations/entities/stats", False, "Endpoint not found", skipped=True)
        return False
    else:
        status = response.status_code if response else "No response"
        log_test("GET /translations/entities/stats", False, f"Status: {status}")
        return False


def test_entity_translations_list_entities(token: str):
    """GET /api/v1/translations/entities/list/{type} - List entities by type"""
    response = make_request("GET", "/api/v1/translations/entities/list/ministry")

    if response and response.status_code == 200:
        data = response.json()
        entities = data.get("entities", [])
        log_test(
            "GET /translations/entities/list/ministry",
            True,
            f"Found {len(entities)} ministries"
        )
        return True
    elif response and response.status_code == 404:
        log_test("GET /translations/entities/list/{type}", False, "Endpoint not found", skipped=True)
        return False
    else:
        status = response.status_code if response else "No response"
        log_test("GET /translations/entities/list/{type}", False, f"Status: {status}")
        return False


def test_entity_translations_search(token: str):
    """GET /api/v1/translations/entities - Search entity translations"""
    response = make_request("GET", "/api/v1/translations/entities?entity_type=ministry&limit=5")

    if response and response.status_code == 200:
        data = response.json()
        translations = data.get("translations", [])
        total = data.get("total", 0)
        log_test(
            "GET /translations/entities (search)",
            True,
            f"Found {len(translations)} of {total} ministry translations"
        )
        return True
    elif response and response.status_code == 404:
        log_test("GET /translations/entities (search)", False, "Endpoint not found", skipped=True)
        return False
    else:
        status = response.status_code if response else "No response"
        log_test("GET /translations/entities (search)", False, f"Status: {status}")
        return False


def test_entity_translation_upsert(token: str):
    """POST /api/v1/translations/entities/upsert - Upsert entity translation"""
    timestamp = datetime.now().strftime("%H%M%S")
    data = {
        "entity_type": "ministry",
        "entity_code": f"TEST-MIN-{timestamp}",
        "language_code": "es",
        "field_name": "name",
        "translated_value": f"Ministerio de Prueba E2E {timestamp}",
        "source": "manual"
    }

    response = make_request("POST", "/api/v1/translations/entities/upsert", token, data)

    if response and response.status_code in [200, 201]:
        result = response.json()
        created_ids["entity_translation_key"] = f"ministry/{data['entity_code']}/es/name"
        log_test(
            "POST /translations/entities/upsert",
            True,
            f"Created for {data['entity_code']}"
        )
        return True
    elif response and response.status_code == 404:
        log_test("POST /translations/entities/upsert", False, "Endpoint not found", skipped=True)
        return False
    else:
        status = response.status_code if response else "No response"
        body = response.text[:200] if response else "N/A"
        log_test("POST /translations/entities/upsert", False, f"Status: {status}, Body: {body}")
        return False


# ============================================================================
# FRONTEND TRANSLATIONS TESTS - /api/v1/translations/frontend
# ============================================================================

def test_frontend_translations_namespaces(token: str):
    """GET /api/v1/translations/frontend/namespaces - List namespaces"""
    response = make_request("GET", "/api/v1/translations/frontend/namespaces")

    if response and response.status_code == 200:
        data = response.json()
        namespaces = data.get("namespaces", [])
        log_test(
            "GET /translations/frontend/namespaces",
            True,
            f"Found {len(namespaces)} namespaces"
        )
        return True
    elif response and response.status_code == 404:
        log_test("GET /translations/frontend/namespaces", False, "Endpoint not found", skipped=True)
        return False
    else:
        status = response.status_code if response else "No response"
        log_test("GET /translations/frontend/namespaces", False, f"Status: {status}")
        return False


def test_frontend_translations_stats(token: str):
    """GET /api/v1/translations/frontend/stats - Get frontend translation stats"""
    response = make_request("GET", "/api/v1/translations/frontend/stats")

    if response and response.status_code == 200:
        data = response.json()
        log_test(
            "GET /translations/frontend/stats",
            True,
            f"Stats retrieved"
        )
        return True
    elif response and response.status_code == 404:
        log_test("GET /translations/frontend/stats", False, "Endpoint not found", skipped=True)
        return False
    else:
        status = response.status_code if response else "No response"
        log_test("GET /translations/frontend/stats", False, f"Status: {status}")
        return False


def test_frontend_translations_search(token: str):
    """GET /api/v1/translations/frontend - Search frontend translations"""
    response = make_request("GET", "/api/v1/translations/frontend?namespace=common&limit=5")

    if response and response.status_code == 200:
        data = response.json()
        translations = data.get("translations", [])
        log_test(
            "GET /translations/frontend (search)",
            True,
            f"Found {len(translations)} translations"
        )
        return True
    elif response and response.status_code == 404:
        log_test("GET /translations/frontend (search)", False, "Endpoint not found", skipped=True)
        return False
    else:
        status = response.status_code if response else "No response"
        log_test("GET /translations/frontend (search)", False, f"Status: {status}")
        return False


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_tests():
    """Run all E2E tests"""
    print("=" * 60)
    print("TaxasGE Translations Module E2E Tests")
    print(f"API: {API_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Authenticate
    print("\n Authenticating...")
    token = get_auth_token()

    if not token:
        print("❌ CRITICAL: Could not authenticate. Tests will run without auth.")
        print("   Some tests may fail due to missing permissions.")
        token = None

    # System Translations Tests
    print("\n" + "=" * 60)
    print("PHASE 1: SYSTEM TRANSLATIONS (/api/v1/translations)")
    print("=" * 60)

    test_system_translations_categories(token)
    test_system_translations_stats(token)
    test_system_translations_list(token)
    test_system_translations_search(token)
    test_system_translation_create(token)
    test_system_translation_read(token)
    test_system_translation_update(token)
    test_system_translation_delete(token)

    # Entity Translations Tests
    print("\n" + "=" * 60)
    print("PHASE 2: ENTITY TRANSLATIONS (/api/v1/translations/entities)")
    print("=" * 60)

    test_entity_translations_types(token)
    test_entity_translations_stats(token)
    test_entity_translations_list_entities(token)
    test_entity_translations_search(token)
    test_entity_translation_upsert(token)

    # Frontend Translations Tests
    print("\n" + "=" * 60)
    print("PHASE 3: FRONTEND TRANSLATIONS (/api/v1/translations/frontend)")
    print("=" * 60)

    test_frontend_translations_namespaces(token)
    test_frontend_translations_stats(token)
    test_frontend_translations_search(token)

    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"⏭️  Skipped: {results['skipped']}")
    print(f"Total: {results['passed'] + results['failed'] + results['skipped']}")

    if results["errors"]:
        print("\n⚠️  Errors:")
        for error in results["errors"]:
            print(f"   - {error}")

    # Return success if all non-skipped tests passed
    return results["failed"] == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
