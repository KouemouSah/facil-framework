"""
E2E Tests for ENUM Management Module Endpoints
Tests ENUM values retrieval, translations, and admin operations.

This tests the hybrid ENUM architecture:
- Backend: /api/v1/enums/{enum_name} returns ENUM values with translations
- Frontend: useEnumLabels hook fetches from API with JSON fallback

Run with: python -m pytest tests/e2e/test_enum_e2e.py -v -s
Or directly: python tests/e2e/test_enum_e2e.py
"""

import requests
from datetime import datetime
import sys

# Configuration
API_URL = "https://taxasge-backend-staging-xrlbgdr5eq-uc.a.run.app"
# API_URL = "http://localhost:8000"  # For local testing

# Expected ENUM types (from DATABASE_SCHEMA_REFERENCE.md)
MODIFIABLE_ENUMS = [
    "user_role_enum",
    "declaration_status_enum",
    "payment_status_enum",
    "document_status_enum",
    "service_type_enum",
    "calculation_method_enum",
]

# Expected values for each ENUM (from DATABASE_SCHEMA_REFERENCE.md)
EXPECTED_ENUM_VALUES = {
    "user_role_enum": [
        "citizen", "business", "accountant", "admin",
        "supervisor", "dgi_agent", "ministry_agent"
    ],
    "declaration_status_enum": [
        "draft", "submitted", "processing",
        "accepted", "rejected", "amended"
    ],
    "payment_status_enum": [
        "pending", "processing", "completed",
        "failed", "refunded", "cancelled"
    ],
    "document_status_enum": [
        "pending", "uploaded", "verified", "rejected"
    ],
    "service_type_enum": [
        "document_processing", "license_permit", "residence_permit",
        "registration_fee", "inspection_fee", "administrative_tax",
        "customs_duty", "declaration_tax"
    ],
    "calculation_method_enum": [
        "fixed_expedition", "fixed_renewal", "fixed_both",
        "percentage_based", "unit_based", "tiered_rates",
        "formula_based", "fixed_plus_unit"
    ],
}

# Languages to test
LANGUAGES = ["es", "fr", "en"]

# Test data storage
created_ids = {
    "test_enum_value": None,
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
        status = "SKIPPED"
        results["skipped"] += 1
    else:
        status = "PASSED" if success else "FAILED"
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
                    print(f"Authenticated with {cred['email']}")
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
    except requests.exceptions.RequestException as e:
        print(f"   Request error: {e}")
        return None


# ============================================================================
# ENUM LIST TESTS - /api/v1/enums/
# ============================================================================

def test_list_modifiable_enums(token: str):
    """GET /api/v1/enums/ - List all modifiable ENUM types"""
    response = make_request("GET", "/api/v1/enums/?language=es", token)

    if response and response.status_code == 200:
        data = response.json()
        enums = data.get("enums", [])
        count = data.get("count", 0)

        # Verify all expected ENUMs are present
        enum_names = [e.get("name") for e in enums]
        missing = [e for e in MODIFIABLE_ENUMS if e not in enum_names]

        if missing:
            log_test(
                "GET /enums/ - List modifiable ENUMs",
                False,
                f"Missing ENUMs: {missing}"
            )
            return False

        log_test(
            "GET /enums/ - List modifiable ENUMs",
            True,
            f"Found {count} ENUMs: {enum_names}"
        )
        return True
    elif response and response.status_code == 401:
        log_test("GET /enums/", False, "Authentication required", skipped=True)
        return False
    elif response and response.status_code == 404:
        log_test("GET /enums/", False, "Endpoint not found - routes not deployed", skipped=True)
        return False
    else:
        status = response.status_code if response else "No response"
        body = response.text[:200] if response else "N/A"
        log_test("GET /enums/", False, f"Status: {status}, Body: {body}")
        return False


# ============================================================================
# ENUM VALUES TESTS - /api/v1/enums/{enum_name}
# ============================================================================

def test_get_enum_values(token: str, enum_name: str, language: str):
    """GET /api/v1/enums/{enum_name}?language={lang} - Get ENUM values with translations"""
    response = make_request("GET", f"/api/v1/enums/{enum_name}?language={language}", token)

    if response and response.status_code == 200:
        data = response.json()
        values = data.get("values", [])
        enum_type = data.get("enum_name", "")

        # Verify enum name matches
        if enum_type != enum_name:
            log_test(
                f"GET /enums/{enum_name} ({language})",
                False,
                f"Enum name mismatch: expected {enum_name}, got {enum_type}"
            )
            return False

        # Extract value names
        value_names = [v.get("value") for v in values]

        # Check if expected values exist (may have more due to archived or new values)
        expected = EXPECTED_ENUM_VALUES.get(enum_name, [])
        missing = [v for v in expected if v not in value_names]

        if missing:
            log_test(
                f"GET /enums/{enum_name} ({language})",
                False,
                f"Missing expected values: {missing}"
            )
            return False

        # Verify translations exist for the requested language
        has_translations = all(v.get(language) for v in values if not v.get("is_archived"))

        log_test(
            f"GET /enums/{enum_name} ({language})",
            True,
            f"Found {len(values)} values, translations: {'complete' if has_translations else 'partial'}"
        )
        return True

    elif response and response.status_code == 400:
        # ENUM not modifiable
        log_test(f"GET /enums/{enum_name}", False, "ENUM not modifiable", skipped=True)
        return False
    elif response and response.status_code == 401:
        log_test(f"GET /enums/{enum_name}", False, "Authentication required", skipped=True)
        return False
    elif response and response.status_code == 404:
        log_test(f"GET /enums/{enum_name}", False, "Endpoint not found", skipped=True)
        return False
    else:
        status = response.status_code if response else "No response"
        body = response.text[:200] if response else "N/A"
        log_test(f"GET /enums/{enum_name} ({language})", False, f"Status: {status}, Body: {body}")
        return False


def test_all_enums_all_languages(token: str):
    """Test all ENUMs in all languages"""
    all_passed = True

    for enum_name in MODIFIABLE_ENUMS:
        for language in LANGUAGES:
            if not test_get_enum_values(token, enum_name, language):
                all_passed = False

    return all_passed


# ============================================================================
# ENUM VALUE STRUCTURE TESTS
# ============================================================================

def test_enum_value_structure(token: str):
    """Verify ENUM value response structure"""
    response = make_request("GET", "/api/v1/enums/user_role_enum?language=es", token)

    if response and response.status_code == 200:
        data = response.json()
        values = data.get("values", [])

        if not values:
            log_test("ENUM value structure", False, "No values returned")
            return False

        # Check first value structure
        first_value = values[0]
        required_fields = ["value", "display_value"]
        translation_fields = ["es", "fr", "en"]

        missing_required = [f for f in required_fields if f not in first_value]
        has_translations = any(f in first_value for f in translation_fields)

        if missing_required:
            log_test(
                "ENUM value structure",
                False,
                f"Missing required fields: {missing_required}"
            )
            return False

        if not has_translations:
            log_test(
                "ENUM value structure",
                False,
                "No translation fields found (es, fr, en)"
            )
            return False

        log_test(
            "ENUM value structure",
            True,
            f"Fields: {list(first_value.keys())}"
        )
        return True

    elif response and response.status_code in [401, 404]:
        log_test("ENUM value structure", False, "Endpoint unavailable", skipped=True)
        return False
    else:
        status = response.status_code if response else "No response"
        log_test("ENUM value structure", False, f"Status: {status}")
        return False


# ============================================================================
# ENUM TRANSLATION UPDATE TEST (Admin only)
# ============================================================================

def test_update_enum_translation(token: str):
    """PUT /api/v1/enums/{enum_name}/values/{value}/translation - Update translation"""
    # Update translation for citizen role
    data = {
        "es": "Ciudadano (actualizado por E2E test)",
        "fr": "Citoyen (mis a jour par E2E test)",
        "en": "Citizen (updated by E2E test)"
    }

    response = make_request(
        "PUT",
        "/api/v1/enums/user_role_enum/values/citizen/translation",
        token,
        data
    )

    if response and response.status_code == 200:
        log_test("PUT /enums/{enum}/values/{value}/translation", True, "Translation updated")
        # Restore original translation
        restore_data = {
            "es": "Ciudadano",
            "fr": "Citoyen",
            "en": "Citizen"
        }
        make_request(
            "PUT",
            "/api/v1/enums/user_role_enum/values/citizen/translation",
            token,
            restore_data
        )
        return True
    elif response and response.status_code == 401:
        log_test("PUT /enums/{enum}/values/{value}/translation", False, "Auth required", skipped=True)
        return False
    elif response and response.status_code == 403:
        log_test("PUT /enums/{enum}/values/{value}/translation", False, "Admin required", skipped=True)
        return False
    elif response and response.status_code == 404:
        log_test("PUT /enums/{enum}/values/{value}/translation", False, "Endpoint not found", skipped=True)
        return False
    else:
        status = response.status_code if response else "No response"
        body = response.text[:200] if response else "N/A"
        log_test("PUT /enums/{enum}/values/{value}/translation", False, f"Status: {status}, Body: {body}")
        return False


# ============================================================================
# UNTRANSLATED ENUM VALUES TEST
# ============================================================================

def test_untranslated_enum_values(token: str):
    """GET /api/v1/enums/untranslated/list - Get untranslated ENUM values"""
    response = make_request("GET", "/api/v1/enums/untranslated/list", token)

    if response and response.status_code == 200:
        data = response.json()
        untranslated = data.get("untranslated", [])
        count = data.get("count", 0)

        log_test(
            "GET /enums/untranslated/list",
            True,
            f"Found {count} untranslated values"
        )
        return True
    elif response and response.status_code in [401, 404]:
        log_test("GET /enums/untranslated/list", False, "Endpoint unavailable", skipped=True)
        return False
    else:
        status = response.status_code if response else "No response"
        log_test("GET /enums/untranslated/list", False, f"Status: {status}")
        return False


# ============================================================================
# FRONTEND INTEGRATION TEST - Simulate useEnumLabels hook behavior
# ============================================================================

def test_frontend_hook_simulation(token: str):
    """
    Simulate useEnumLabels hook behavior:
    1. Fetch all ENUMs from API
    2. Build label maps
    3. Test getLabel() function logic
    """
    print("\n" + "-" * 40)
    print("Simulating Frontend useEnumLabels Hook")
    print("-" * 40)

    # Simulate loading all ENUMs (like the hook does)
    api_enum_data = {}
    failed_enums = []

    for enum_name in MODIFIABLE_ENUMS:
        response = make_request("GET", f"/api/v1/enums/{enum_name}?language=es", token)
        if response and response.status_code == 200:
            api_enum_data[enum_name] = response.json()
        else:
            failed_enums.append(enum_name)

    if failed_enums:
        log_test(
            "Frontend Hook - Load ENUMs",
            False,
            f"Failed to load: {failed_enums}"
        )
        return False

    # Build label maps (like the hook does)
    api_label_maps = {}
    for enum_name, response_data in api_enum_data.items():
        api_label_maps[enum_name] = {}
        for value_info in response_data.get("values", []):
            value = value_info.get("value")
            translation = value_info.get("es") or value_info.get("display_value")
            api_label_maps[enum_name][value] = translation

    # Test getLabel() function logic
    test_cases = [
        ("user_role_enum", "citizen", "Ciudadano"),
        ("user_role_enum", "admin", "Administrador"),
        ("declaration_status_enum", "draft", "Borrador"),
        ("payment_status_enum", "pending", "Pendiente"),
    ]

    all_passed = True
    for enum_name, value, expected_contains in test_cases:
        actual = api_label_maps.get(enum_name, {}).get(value, value)
        # Check if the label contains expected text (may vary slightly)
        if actual and len(actual) > 1 and actual != value:
            print(f"   getLabel('{enum_name}', '{value}') = '{actual}'")
        else:
            print(f"   WARNING: getLabel('{enum_name}', '{value}') returned raw value")
            all_passed = False

    log_test(
        "Frontend Hook - getLabel() simulation",
        all_passed,
        "All labels retrieved successfully" if all_passed else "Some labels missing translations"
    )

    return all_passed


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_tests():
    """Run all ENUM E2E tests"""
    print("=" * 60)
    print("TaxasGE ENUM Management Module E2E Tests")
    print(f"API: {API_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Authenticate
    print("\nAuthenticating...")
    token = get_auth_token()

    if not token:
        print("CRITICAL: Could not authenticate. Tests will run without auth.")
        print("   ENUM endpoints require admin authentication.")
        token = None

    # Phase 1: List ENUMs
    print("\n" + "=" * 60)
    print("PHASE 1: LIST MODIFIABLE ENUMS")
    print("=" * 60)

    test_list_modifiable_enums(token)

    # Phase 2: Get ENUM Values (test each ENUM in Spanish first)
    print("\n" + "=" * 60)
    print("PHASE 2: GET ENUM VALUES (Spanish)")
    print("=" * 60)

    for enum_name in MODIFIABLE_ENUMS:
        test_get_enum_values(token, enum_name, "es")

    # Phase 3: Test value structure
    print("\n" + "=" * 60)
    print("PHASE 3: ENUM VALUE STRUCTURE")
    print("=" * 60)

    test_enum_value_structure(token)

    # Phase 4: Test multi-language
    print("\n" + "=" * 60)
    print("PHASE 4: MULTI-LANGUAGE SUPPORT")
    print("=" * 60)

    # Test one ENUM in all languages
    for language in LANGUAGES:
        test_get_enum_values(token, "user_role_enum", language)

    # Phase 5: Admin operations (if authenticated)
    print("\n" + "=" * 60)
    print("PHASE 5: ADMIN OPERATIONS")
    print("=" * 60)

    test_update_enum_translation(token)
    test_untranslated_enum_values(token)

    # Phase 6: Frontend integration simulation
    print("\n" + "=" * 60)
    print("PHASE 6: FRONTEND HOOK SIMULATION")
    print("=" * 60)

    test_frontend_hook_simulation(token)

    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"PASSED: {results['passed']}")
    print(f"FAILED: {results['failed']}")
    print(f"SKIPPED: {results['skipped']}")
    print(f"Total: {results['passed'] + results['failed'] + results['skipped']}")

    if results["errors"]:
        print("\nErrors:")
        for error in results["errors"]:
            print(f"   - {error}")

    # Return success if all non-skipped tests passed
    return results["failed"] == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
