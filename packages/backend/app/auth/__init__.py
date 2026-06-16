"""auth — credentials (password/TOTP) + native auth flows (D4.2).

Core (always-on) infrastructure. Password hashing (bcrypt) and TOTP utilities
here; token issuance is the NativeAuthProvider (app/core/providers/auth_native).
Replaces the bootstrap admin-token gate with real authentication.
"""
