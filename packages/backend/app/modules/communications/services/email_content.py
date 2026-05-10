"""
Email Content - Translated content for email templates

Supports:
- Spanish (es) - Default
- French (fr)
- English (en)

All email content for i18n support
"""

from typing import Dict, Any


# ============================================================================
# EMAIL CONTENT DATABASE - Multilingual
# ============================================================================

EMAIL_CONTENT: Dict[str, Dict[str, Dict[str, str]]] = {
    # ========================================================================
    # VERIFICATION EMAIL
    # ========================================================================
    "verification_email": {
        "es": {
            "subject": "Facil - Verifica tu dirección de correo electrónico",
            "title": "Verificación de correo electrónico",
            "greeting": "Hola {user_name},",
            "greeting_default": "Hola,",
            "message": "Gracias por registrarte en Facil. Por favor verifica tu dirección de correo electrónico ingresando el siguiente código:",
            "expiry_label": "Este código expirará en:",
            "expiry_time": "15 minutos",
            "ignore_text": "Si no solicitaste este código, por favor ignora este correo electrónico.",
            "footer_text": "Este es un mensaje automático de la plataforma Facil. Por favor no respondas a este correo.",
            "support_text": "Soporte",
            "rights_reserved": "Todos los derechos reservados",
        },
        "fr": {
            "subject": "Facil - Vérifiez votre adresse e-mail",
            "title": "Vérification d'e-mail",
            "greeting": "Bonjour {user_name},",
            "greeting_default": "Bonjour,",
            "message": "Merci de vous être inscrit sur Facil. Veuillez vérifier votre adresse e-mail en saisissant le code suivant :",
            "expiry_label": "Ce code expirera dans :",
            "expiry_time": "15 minutes",
            "ignore_text": "Si vous n'avez pas demandé ce code, veuillez ignorer cet e-mail.",
            "footer_text": "Ceci est un message automatique de la plateforme Facil. Veuillez ne pas répondre à cet e-mail.",
            "support_text": "Support",
            "rights_reserved": "Tous droits réservés",
        },
        "en": {
            "subject": "Facil - Verify Your Email Address",
            "title": "Email Verification",
            "greeting": "Hello {user_name},",
            "greeting_default": "Hello,",
            "message": "Thank you for registering with Facil. Please verify your email address by entering the following code:",
            "expiry_label": "This code will expire in:",
            "expiry_time": "15 minutes",
            "ignore_text": "If you didn't request this code, please ignore this email.",
            "footer_text": "This is an automated message from Facil Platform. Please do not reply to this email.",
            "support_text": "Support",
            "rights_reserved": "All rights reserved",
        },
    },

    # ========================================================================
    # PASSWORD RESET
    # ========================================================================
    "password_reset": {
        "es": {
            "subject": "Facil - Solicitud de restablecimiento de contraseña",
            "title": "Solicitud de restablecimiento de contraseña",
            "greeting": "Hola {user_name},",
            "greeting_default": "Hola,",
            "message": "Recibimos una solicitud para restablecer la contraseña de tu cuenta Facil.",
            "button_text": "Restablecer contraseña",
            "or_copy_text": "O copia y pega este enlace en tu navegador:",
            "expiry_label": "Este enlace expirará en:",
            "expiry_time": "1 hora",
            "ignore_text": "Si no solicitaste restablecer tu contraseña, por favor ignora este correo y tu contraseña permanecerá sin cambios.",
            "footer_text": "Este es un mensaje automático de la plataforma Facil. Por favor no respondas a este correo.",
            "support_text": "Soporte",
            "rights_reserved": "Todos los derechos reservados",
        },
        "fr": {
            "subject": "Facil - Demande de réinitialisation de mot de passe",
            "title": "Demande de réinitialisation de mot de passe",
            "greeting": "Bonjour {user_name},",
            "greeting_default": "Bonjour,",
            "message": "Nous avons reçu une demande de réinitialisation du mot de passe de votre compte Facil.",
            "button_text": "Réinitialiser le mot de passe",
            "or_copy_text": "Ou copiez et collez ce lien dans votre navigateur :",
            "expiry_label": "Ce lien expirera dans :",
            "expiry_time": "1 heure",
            "ignore_text": "Si vous n'avez pas demandé à réinitialiser votre mot de passe, veuillez ignorer cet e-mail et votre mot de passe restera inchangé.",
            "footer_text": "Ceci est un message automatique de la plateforme Facil. Veuillez ne pas répondre à cet e-mail.",
            "support_text": "Support",
            "rights_reserved": "Tous droits réservés",
        },
        "en": {
            "subject": "Facil - Password Reset Request",
            "title": "Password Reset Request",
            "greeting": "Hello {user_name},",
            "greeting_default": "Hello,",
            "message": "We received a request to reset your password for your Facil account.",
            "button_text": "Reset Password",
            "or_copy_text": "Or copy and paste this link into your browser:",
            "expiry_label": "This link will expire in:",
            "expiry_time": "1 hour",
            "ignore_text": "If you didn't request a password reset, please ignore this email and your password will remain unchanged.",
            "footer_text": "This is an automated message from Facil Platform. Please do not reply to this email.",
            "support_text": "Support",
            "rights_reserved": "All rights reserved",
        },
    },

    # ========================================================================
    # PASSWORD RESET CONFIRMATION
    # ========================================================================
    "password_reset_confirmation": {
        "es": {
            "subject": "Facil - Contraseña restablecida exitosamente",
            "title": "Restablecimiento de contraseña exitoso",
            "greeting": "Hola {user_name},",
            "greeting_default": "Hola,",
            "message": "Tu contraseña ha sido restablecida exitosamente.",
            "login_message": "Ahora puedes iniciar sesión en tu cuenta Facil usando tu nueva contraseña.",
            "button_text": "Iniciar sesión en Facil",
            "warning_text": "Si no realizaste este cambio, por favor contacta a nuestro equipo de soporte inmediatamente.",
            "footer_text": "Este es un mensaje automático de la plataforma Facil. Por favor no respondas a este correo.",
            "support_text": "Soporte",
            "rights_reserved": "Todos los derechos reservados",
        },
        "fr": {
            "subject": "Facil - Mot de passe réinitialisé avec succès",
            "title": "Réinitialisation du mot de passe réussie",
            "greeting": "Bonjour {user_name},",
            "greeting_default": "Bonjour,",
            "message": "Votre mot de passe a été réinitialisé avec succès.",
            "login_message": "Vous pouvez maintenant vous connecter à votre compte Facil avec votre nouveau mot de passe.",
            "button_text": "Se connecter à Facil",
            "warning_text": "Si vous n'avez pas effectué cette modification, veuillez contacter notre équipe d'assistance immédiatement.",
            "footer_text": "Ceci est un message automatique de la plateforme Facil. Veuillez ne pas répondre à cet e-mail.",
            "support_text": "Support",
            "rights_reserved": "Tous droits réservés",
        },
        "en": {
            "subject": "Facil - Password Successfully Reset",
            "title": "Password Reset Successful",
            "greeting": "Hello {user_name},",
            "greeting_default": "Hello,",
            "message": "Your password has been successfully reset.",
            "login_message": "You can now log in to your Facil account using your new password.",
            "button_text": "Log In to Facil",
            "warning_text": "If you didn't make this change, please contact our support team immediately.",
            "footer_text": "This is an automated message from Facil Platform. Please do not reply to this email.",
            "support_text": "Support",
            "rights_reserved": "All rights reserved",
        },
    },

    # ========================================================================
    # 2FA CODE
    # ========================================================================
    "2fa_code": {
        "es": {
            "subject": "Facil - Código de autenticación de dos factores",
            "title": "Autenticación de dos factores",
            "greeting": "Hola {user_name},",
            "greeting_default": "Hola,",
            "message": "Tu código de autenticación de dos factores es:",
            "expiry_label": "Este código expirará en:",
            "expiry_time": "5 minutos",
            "security_warning": "Si no solicitaste este código, alguien podría estar intentando acceder a tu cuenta. Por favor asegura tu cuenta inmediatamente.",
            "footer_text": "Este es un mensaje automático de la plataforma Facil. Por favor no respondas a este correo.",
            "support_text": "Soporte",
            "rights_reserved": "Todos los derechos reservados",
        },
        "fr": {
            "subject": "Facil - Code d'authentification à deux facteurs",
            "title": "Authentification à deux facteurs",
            "greeting": "Bonjour {user_name},",
            "greeting_default": "Bonjour,",
            "message": "Votre code d'authentification à deux facteurs est :",
            "expiry_label": "Ce code expirera dans :",
            "expiry_time": "5 minutes",
            "security_warning": "Si vous n'avez pas demandé ce code, quelqu'un pourrait essayer d'accéder à votre compte. Veuillez sécuriser votre compte immédiatement.",
            "footer_text": "Ceci est un message automatique de la plateforme Facil. Veuillez ne pas répondre à cet e-mail.",
            "support_text": "Support",
            "rights_reserved": "Tous droits réservés",
        },
        "en": {
            "subject": "Facil - Two-Factor Authentication Code",
            "title": "Two-Factor Authentication",
            "greeting": "Hello {user_name},",
            "greeting_default": "Hello,",
            "message": "Your two-factor authentication code is:",
            "expiry_label": "This code will expire in:",
            "expiry_time": "5 minutes",
            "security_warning": "If you didn't request this code, someone may be trying to access your account. Please secure your account immediately.",
            "footer_text": "This is an automated message from Facil Platform. Please do not reply to this email.",
            "support_text": "Support",
            "rights_reserved": "All rights reserved",
        },
    },

    # ========================================================================
    # ACCOUNT LOCKOUT
    # ========================================================================
    "account_lockout": {
        "es": {
            "subject": "Facil - Cuenta bloqueada temporalmente",
            "title": "Cuenta bloqueada temporalmente",
            "greeting": "Hola {user_name},",
            "greeting_default": "Hola,",
            "message": "Tu cuenta Facil ha sido bloqueada temporalmente debido a múltiples intentos de inicio de sesión fallidos.",
            "lockout_duration": "Tu cuenta se desbloqueará automáticamente en {minutes} minutos.",
            "if_you_label": "Si fuiste tú:",
            "if_you_message": "Por favor espera {minutes} minutos antes de intentar iniciar sesión nuevamente. Asegúrate de usar la contraseña correcta.",
            "if_not_you_label": "Si no fuiste tú:",
            "if_not_you_message": "Alguien podría estar intentando acceder a tu cuenta. Recomendamos cambiar tu contraseña después de que expire el período de bloqueo.",
            "footer_text": "Este es un mensaje de seguridad automático de la plataforma Facil. Por favor no respondas a este correo.",
            "support_text": "Soporte",
            "rights_reserved": "Todos los derechos reservados",
        },
        "fr": {
            "subject": "Facil - Compte temporairement verrouillé",
            "title": "Compte temporairement verrouillé",
            "greeting": "Bonjour {user_name},",
            "greeting_default": "Bonjour,",
            "message": "Votre compte Facil a été temporairement verrouillé en raison de plusieurs tentatives de connexion infructueuses.",
            "lockout_duration": "Votre compte sera automatiquement déverrouillé dans {minutes} minutes.",
            "if_you_label": "Si c'était vous :",
            "if_you_message": "Veuillez attendre {minutes} minutes avant de réessayer de vous connecter. Assurez-vous d'utiliser le bon mot de passe.",
            "if_not_you_label": "Si ce n'était pas vous :",
            "if_not_you_message": "Quelqu'un pourrait essayer d'accéder à votre compte. Nous recommandons de changer votre mot de passe après l'expiration de la période de verrouillage.",
            "footer_text": "Ceci est un message de sécurité automatique de la plateforme Facil. Veuillez ne pas répondre à cet e-mail.",
            "support_text": "Support",
            "rights_reserved": "Tous droits réservés",
        },
        "en": {
            "subject": "Facil - Account Temporarily Locked",
            "title": "Account Temporarily Locked",
            "greeting": "Hello {user_name},",
            "greeting_default": "Hello,",
            "message": "Your Facil account has been temporarily locked due to multiple failed login attempts.",
            "lockout_duration": "Your account will be automatically unlocked in {minutes} minutes.",
            "if_you_label": "If this was you:",
            "if_you_message": "Please wait {minutes} minutes before trying to log in again. Make sure you're using the correct password.",
            "if_not_you_label": "If this wasn't you:",
            "if_not_you_message": "Someone may be trying to access your account. We recommend changing your password after the lockout period expires.",
            "footer_text": "This is an automated security message from Facil Platform. Please do not reply to this email.",
            "support_text": "Support",
            "rights_reserved": "All rights reserved",
        },
    },

    # ========================================================================
    # AGENT INVITATION
    # ========================================================================
    "agent_invitation": {
        "es": {
            "subject": "Facil - Invitación para ser Agente",
            "title": "Invitación para ser Agente Facil",
            "greeting": "Hola {user_name},",
            "greeting_default": "Hola,",
            "message": "Has sido invitado/a a unirte a la plataforma Facil como Agente. Para completar tu registro, utiliza el siguiente código de verificación:",
            "instructions": "Haz clic en el botón de abajo para activar tu cuenta y establecer tu contraseña.",
            "button_text": "Activar mi cuenta",
            "or_copy_text": "O copia y pega este enlace en tu navegador:",
            "expiry_label": "Este código expirará en:",
            "expiry_time": "24 horas",
            "ignore_text": "Si no esperabas esta invitación, por favor ignora este correo electrónico.",
            "footer_text": "Este es un mensaje automático de la plataforma Facil. Por favor no respondas a este correo.",
            "support_text": "Soporte",
            "rights_reserved": "Todos los derechos reservados",
        },
        "fr": {
            "subject": "Facil - Invitation Agent",
            "title": "Invitation Agent Facil",
            "greeting": "Bonjour {user_name},",
            "greeting_default": "Bonjour,",
            "message": "Vous avez été invité(e) à rejoindre la plateforme Facil en tant qu'Agent. Pour compléter votre inscription, utilisez le code de vérification suivant :",
            "instructions": "Cliquez sur le bouton ci-dessous pour activer votre compte et définir votre mot de passe.",
            "button_text": "Activer mon compte",
            "or_copy_text": "Ou copiez et collez ce lien dans votre navigateur :",
            "expiry_label": "Ce code expirera dans :",
            "expiry_time": "24 heures",
            "ignore_text": "Si vous n'attendiez pas cette invitation, veuillez ignorer cet e-mail.",
            "footer_text": "Ceci est un message automatique de la plateforme Facil. Veuillez ne pas répondre à cet e-mail.",
            "support_text": "Support",
            "rights_reserved": "Tous droits réservés",
        },
        "en": {
            "subject": "Facil - Agent Invitation",
            "title": "Facil Agent Invitation",
            "greeting": "Hello {user_name},",
            "greeting_default": "Hello,",
            "message": "You have been invited to join the Facil platform as an Agent. To complete your registration, use the following verification code:",
            "instructions": "Click the button below to activate your account and set your password.",
            "button_text": "Activate my account",
            "or_copy_text": "Or copy and paste this link into your browser:",
            "expiry_label": "This code will expire in:",
            "expiry_time": "24 hours",
            "ignore_text": "If you were not expecting this invitation, please ignore this email.",
            "footer_text": "This is an automated message from Facil Platform. Please do not reply to this email.",
            "support_text": "Support",
            "rights_reserved": "All rights reserved",
        },
    },

    # ========================================================================
    # ADMIN INVITATION
    # ========================================================================
    "admin_invitation": {
        "es": {
            "subject": "Facil - Invitación para ser Administrador",
            "title": "Invitación para ser Administrador Facil",
            "greeting": "Hola {user_name},",
            "greeting_default": "Hola,",
            "message": "Has sido invitado/a a unirte a la plataforma Facil como Administrador. Para completar tu registro, utiliza el siguiente código de verificación:",
            "instructions": "Haz clic en el botón de abajo para activar tu cuenta y establecer tu contraseña.",
            "button_text": "Activar mi cuenta",
            "or_copy_text": "O copia y pega este enlace en tu navegador:",
            "expiry_label": "Este código expirará en:",
            "expiry_time": "24 horas",
            "ignore_text": "Si no esperabas esta invitación, por favor ignora este correo electrónico.",
            "footer_text": "Este es un mensaje automático de la plataforma Facil. Por favor no respondas a este correo.",
            "support_text": "Soporte",
            "rights_reserved": "Todos los derechos reservados",
        },
        "fr": {
            "subject": "Facil - Invitation Administrateur",
            "title": "Invitation Administrateur Facil",
            "greeting": "Bonjour {user_name},",
            "greeting_default": "Bonjour,",
            "message": "Vous avez été invité(e) à rejoindre la plateforme Facil en tant qu'Administrateur. Pour compléter votre inscription, utilisez le code de vérification suivant :",
            "instructions": "Cliquez sur le bouton ci-dessous pour activer votre compte et définir votre mot de passe.",
            "button_text": "Activer mon compte",
            "or_copy_text": "Ou copiez et collez ce lien dans votre navigateur :",
            "expiry_label": "Ce code expirera dans :",
            "expiry_time": "24 heures",
            "ignore_text": "Si vous n'attendiez pas cette invitation, veuillez ignorer cet e-mail.",
            "footer_text": "Ceci est un message automatique de la plateforme Facil. Veuillez ne pas répondre à cet e-mail.",
            "support_text": "Support",
            "rights_reserved": "Tous droits réservés",
        },
        "en": {
            "subject": "Facil - Administrator Invitation",
            "title": "Facil Administrator Invitation",
            "greeting": "Hello {user_name},",
            "greeting_default": "Hello,",
            "message": "You have been invited to join the Facil platform as an Administrator. To complete your registration, use the following verification code:",
            "instructions": "Click the button below to activate your account and set your password.",
            "button_text": "Activate my account",
            "or_copy_text": "Or copy and paste this link into your browser:",
            "expiry_label": "This code will expire in:",
            "expiry_time": "24 hours",
            "ignore_text": "If you were not expecting this invitation, please ignore this email.",
            "footer_text": "This is an automated message from Facil Platform. Please do not reply to this email.",
            "support_text": "Support",
            "rights_reserved": "All rights reserved",
        },
    },
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_email_content(email_type: str, language: str = "es") -> Dict[str, str]:
    """
    Get email content for specified type and language

    Args:
        email_type: Type of email (verification_email, password_reset, etc.)
        language: Language code (es/fr/en)

    Returns:
        Dictionary with email content

    Raises:
        ValueError: If email_type or language not found
    """
    if email_type not in EMAIL_CONTENT:
        raise ValueError(f"Unknown email type: {email_type}")

    if language not in EMAIL_CONTENT[email_type]:
        # Fallback to Spanish
        language = "es"

    return EMAIL_CONTENT[email_type][language]


def get_supported_languages() -> list[str]:
    """
    Get list of supported languages

    Returns:
        List of language codes
    """
    return ["es", "fr", "en"]
