"""
WorkflowNotificationService - Notifications for service request workflows.

Integrates with the communications module to send:
- Email notifications
- SMS notifications
- Push notifications

For workflow-specific events like:
- Request submitted
- Request approved/rejected
- Documents required
- Payment confirmation
- Appointment scheduled
"""
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
import logging
import asyncpg

from ...communications.services.communication_service import CommunicationService
from ...communications.models.communication import CommunicationType
from ..models.enums import ServiceRequestStatus, WorkflowCode

logger = logging.getLogger(__name__)


class NotificationChannel:
    """Available notification channels"""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    ALL = "all"


class NotificationType:
    """Types of workflow notifications"""
    REQUEST_SUBMITTED = "request_submitted"
    REQUEST_APPROVED = "request_approved"
    REQUEST_REJECTED = "request_rejected"
    DOCUMENTS_REQUIRED = "documents_required"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_CONFIRMED = "payment_confirmed"
    PAYMENT_FAILED = "payment_failed"
    APPOINTMENT_SCHEDULED = "appointment_scheduled"
    REQUEST_COMPLETED = "request_completed"
    STATUS_CHANGED = "status_changed"
    REMINDER = "reminder"


class WorkflowNotificationService:
    """
    Handles workflow-specific notifications.

    Uses the communications module for actual sending,
    but provides workflow-specific templates and logic.
    """

    def __init__(self):
        self.communication_service = CommunicationService()
        self._templates: Dict[str, Dict[str, str]] = self._load_templates()

    def _load_templates(self) -> Dict[str, Dict[str, str]]:
        """Load notification templates."""
        return {
            NotificationType.REQUEST_SUBMITTED: {
                "subject_es": "Solicitud registrada - {reference}",
                "subject_fr": "Demande enregistrée - {reference}",
                "body_es": """
                    <h2>Su solicitud ha sido registrada</h2>
                    <p>Estimado/a {user_name},</p>
                    <p>Su solicitud de <strong>{workflow_name}</strong> ha sido registrada con éxito.</p>
                    <p><strong>Número de referencia:</strong> {reference}</p>
                    <p><strong>Fecha:</strong> {date}</p>
                    <p>Le mantendremos informado sobre el estado de su solicitud.</p>
                    <p>Atentamente,<br>Equipo TaxasGE</p>
                """,
                "body_fr": """
                    <h2>Votre demande a été enregistrée</h2>
                    <p>Cher/Chère {user_name},</p>
                    <p>Votre demande de <strong>{workflow_name}</strong> a été enregistrée avec succès.</p>
                    <p><strong>Numéro de référence:</strong> {reference}</p>
                    <p><strong>Date:</strong> {date}</p>
                    <p>Nous vous tiendrons informé de l'état de votre demande.</p>
                    <p>Cordialement,<br>Équipe TaxasGE</p>
                """,
                "sms_es": "TaxasGE: Su solicitud {reference} ha sido registrada. Consulte su correo para más detalles.",
                "sms_fr": "TaxasGE: Votre demande {reference} a été enregistrée. Consultez votre email pour plus de détails."
            },
            NotificationType.REQUEST_APPROVED: {
                "subject_es": "Solicitud aprobada - {reference}",
                "subject_fr": "Demande approuvée - {reference}",
                "body_es": """
                    <h2>Su solicitud ha sido aprobada</h2>
                    <p>Estimado/a {user_name},</p>
                    <p>Su solicitud de <strong>{workflow_name}</strong> ha sido aprobada.</p>
                    <p><strong>Número de referencia:</strong> {reference}</p>
                    <p>{next_steps}</p>
                    <p>Atentamente,<br>Equipo TaxasGE</p>
                """,
                "body_fr": """
                    <h2>Votre demande a été approuvée</h2>
                    <p>Cher/Chère {user_name},</p>
                    <p>Votre demande de <strong>{workflow_name}</strong> a été approuvée.</p>
                    <p><strong>Numéro de référence:</strong> {reference}</p>
                    <p>{next_steps}</p>
                    <p>Cordialement,<br>Équipe TaxasGE</p>
                """,
                "sms_es": "TaxasGE: Su solicitud {reference} ha sido APROBADA. Consulte su correo para próximos pasos.",
                "sms_fr": "TaxasGE: Votre demande {reference} a été APPROUVÉE. Consultez votre email pour les prochaines étapes."
            },
            NotificationType.REQUEST_REJECTED: {
                "subject_es": "Solicitud rechazada - {reference}",
                "subject_fr": "Demande rejetée - {reference}",
                "body_es": """
                    <h2>Su solicitud ha sido rechazada</h2>
                    <p>Estimado/a {user_name},</p>
                    <p>Lamentamos informarle que su solicitud de <strong>{workflow_name}</strong> ha sido rechazada.</p>
                    <p><strong>Número de referencia:</strong> {reference}</p>
                    <p><strong>Motivo:</strong> {rejection_reason}</p>
                    <p>Puede presentar una nueva solicitud corrigiendo los problemas indicados.</p>
                    <p>Atentamente,<br>Equipo TaxasGE</p>
                """,
                "body_fr": """
                    <h2>Votre demande a été rejetée</h2>
                    <p>Cher/Chère {user_name},</p>
                    <p>Nous regrettons de vous informer que votre demande de <strong>{workflow_name}</strong> a été rejetée.</p>
                    <p><strong>Numéro de référence:</strong> {reference}</p>
                    <p><strong>Motif:</strong> {rejection_reason}</p>
                    <p>Vous pouvez soumettre une nouvelle demande en corrigeant les problèmes indiqués.</p>
                    <p>Cordialement,<br>Équipe TaxasGE</p>
                """,
                "sms_es": "TaxasGE: Su solicitud {reference} ha sido RECHAZADA. Motivo: {rejection_reason}. Consulte su correo.",
                "sms_fr": "TaxasGE: Votre demande {reference} a été REJETÉE. Motif: {rejection_reason}. Consultez votre email."
            },
            NotificationType.DOCUMENTS_REQUIRED: {
                "subject_es": "Documentos adicionales requeridos - {reference}",
                "subject_fr": "Documents supplémentaires requis - {reference}",
                "body_es": """
                    <h2>Documentos adicionales requeridos</h2>
                    <p>Estimado/a {user_name},</p>
                    <p>Se requieren documentos adicionales para su solicitud de <strong>{workflow_name}</strong>.</p>
                    <p><strong>Número de referencia:</strong> {reference}</p>
                    <p><strong>Documentos requeridos:</strong></p>
                    <ul>{documents_list}</ul>
                    <p>Por favor, cargue estos documentos en su cuenta.</p>
                    <p>Atentamente,<br>Equipo TaxasGE</p>
                """,
                "body_fr": """
                    <h2>Documents supplémentaires requis</h2>
                    <p>Cher/Chère {user_name},</p>
                    <p>Des documents supplémentaires sont requis pour votre demande de <strong>{workflow_name}</strong>.</p>
                    <p><strong>Numéro de référence:</strong> {reference}</p>
                    <p><strong>Documents requis:</strong></p>
                    <ul>{documents_list}</ul>
                    <p>Veuillez télécharger ces documents dans votre compte.</p>
                    <p>Cordialement,<br>Équipe TaxasGE</p>
                """,
                "sms_es": "TaxasGE: Documentos adicionales requeridos para {reference}. Acceda a su cuenta para más detalles.",
                "sms_fr": "TaxasGE: Documents supplémentaires requis pour {reference}. Accédez à votre compte pour plus de détails."
            },
            NotificationType.PAYMENT_PENDING: {
                "subject_es": "Pago pendiente - {reference}",
                "subject_fr": "Paiement en attente - {reference}",
                "body_es": """
                    <h2>Pago pendiente</h2>
                    <p>Estimado/a {user_name},</p>
                    <p>Su solicitud de <strong>{workflow_name}</strong> requiere el pago de tasas.</p>
                    <p><strong>Número de referencia:</strong> {reference}</p>
                    <p><strong>Monto:</strong> {amount} XAF</p>
                    <p>Puede realizar el pago mediante Mobile Money (MTN, Orange, BANGE).</p>
                    <p>Atentamente,<br>Equipo TaxasGE</p>
                """,
                "body_fr": """
                    <h2>Paiement en attente</h2>
                    <p>Cher/Chère {user_name},</p>
                    <p>Votre demande de <strong>{workflow_name}</strong> nécessite le paiement de frais.</p>
                    <p><strong>Numéro de référence:</strong> {reference}</p>
                    <p><strong>Montant:</strong> {amount} XAF</p>
                    <p>Vous pouvez effectuer le paiement via Mobile Money (MTN, Orange, BANGE).</p>
                    <p>Cordialement,<br>Équipe TaxasGE</p>
                """,
                "sms_es": "TaxasGE: Pago de {amount} XAF pendiente para {reference}. Pague con Mobile Money.",
                "sms_fr": "TaxasGE: Paiement de {amount} XAF en attente pour {reference}. Payez par Mobile Money."
            },
            NotificationType.PAYMENT_CONFIRMED: {
                "subject_es": "Pago confirmado - {reference}",
                "subject_fr": "Paiement confirmé - {reference}",
                "body_es": """
                    <h2>Pago confirmado</h2>
                    <p>Estimado/a {user_name},</p>
                    <p>Hemos recibido su pago para la solicitud de <strong>{workflow_name}</strong>.</p>
                    <p><strong>Número de referencia:</strong> {reference}</p>
                    <p><strong>Monto:</strong> {amount} XAF</p>
                    <p><strong>ID de transacción:</strong> {transaction_id}</p>
                    <p>Su solicitud será procesada a la brevedad.</p>
                    <p>Atentamente,<br>Equipo TaxasGE</p>
                """,
                "body_fr": """
                    <h2>Paiement confirmé</h2>
                    <p>Cher/Chère {user_name},</p>
                    <p>Nous avons reçu votre paiement pour la demande de <strong>{workflow_name}</strong>.</p>
                    <p><strong>Numéro de référence:</strong> {reference}</p>
                    <p><strong>Montant:</strong> {amount} XAF</p>
                    <p><strong>ID de transaction:</strong> {transaction_id}</p>
                    <p>Votre demande sera traitée dans les plus brefs délais.</p>
                    <p>Cordialement,<br>Équipe TaxasGE</p>
                """,
                "sms_es": "TaxasGE: Pago de {amount} XAF confirmado para {reference}. Su solicitud será procesada.",
                "sms_fr": "TaxasGE: Paiement de {amount} XAF confirmé pour {reference}. Votre demande sera traitée."
            },
            NotificationType.APPOINTMENT_SCHEDULED: {
                "subject_es": "Cita programada - {reference}",
                "subject_fr": "Rendez-vous programmé - {reference}",
                "body_es": """
                    <h2>Cita programada</h2>
                    <p>Estimado/a {user_name},</p>
                    <p>Se ha programado una cita para su solicitud de <strong>{workflow_name}</strong>.</p>
                    <p><strong>Número de referencia:</strong> {reference}</p>
                    <p><strong>Fecha:</strong> {appointment_date}</p>
                    <p><strong>Hora:</strong> {appointment_time}</p>
                    <p><strong>Lugar:</strong> {appointment_location}</p>
                    <p><strong>Documentos a llevar:</strong></p>
                    <ul>{documents_to_bring}</ul>
                    <p>Atentamente,<br>Equipo TaxasGE</p>
                """,
                "body_fr": """
                    <h2>Rendez-vous programmé</h2>
                    <p>Cher/Chère {user_name},</p>
                    <p>Un rendez-vous a été programmé pour votre demande de <strong>{workflow_name}</strong>.</p>
                    <p><strong>Numéro de référence:</strong> {reference}</p>
                    <p><strong>Date:</strong> {appointment_date}</p>
                    <p><strong>Heure:</strong> {appointment_time}</p>
                    <p><strong>Lieu:</strong> {appointment_location}</p>
                    <p><strong>Documents à apporter:</strong></p>
                    <ul>{documents_to_bring}</ul>
                    <p>Cordialement,<br>Équipe TaxasGE</p>
                """,
                "sms_es": "TaxasGE: Cita para {reference} el {appointment_date} a las {appointment_time} en {appointment_location}.",
                "sms_fr": "TaxasGE: RDV pour {reference} le {appointment_date} à {appointment_time} à {appointment_location}."
            },
            NotificationType.REQUEST_COMPLETED: {
                "subject_es": "Solicitud completada - {reference}",
                "subject_fr": "Demande terminée - {reference}",
                "body_es": """
                    <h2>Solicitud completada</h2>
                    <p>Estimado/a {user_name},</p>
                    <p>Su solicitud de <strong>{workflow_name}</strong> ha sido completada con éxito.</p>
                    <p><strong>Número de referencia:</strong> {reference}</p>
                    <p>{completion_message}</p>
                    <p>Gracias por usar TaxasGE.</p>
                    <p>Atentamente,<br>Equipo TaxasGE</p>
                """,
                "body_fr": """
                    <h2>Demande terminée</h2>
                    <p>Cher/Chère {user_name},</p>
                    <p>Votre demande de <strong>{workflow_name}</strong> a été complétée avec succès.</p>
                    <p><strong>Numéro de référence:</strong> {reference}</p>
                    <p>{completion_message}</p>
                    <p>Merci d'utiliser TaxasGE.</p>
                    <p>Cordialement,<br>Équipe TaxasGE</p>
                """,
                "sms_es": "TaxasGE: Su solicitud {reference} ha sido COMPLETADA. Gracias por usar TaxasGE.",
                "sms_fr": "TaxasGE: Votre demande {reference} a été COMPLÉTÉE. Merci d'utiliser TaxasGE."
            }
        }

    async def send_notification(
        self,
        db: asyncpg.Connection,
        notification_type: str,
        user_id: UUID,
        data: Dict[str, Any],
        channels: List[str] = None,
        language: str = "es"
    ) -> bool:
        """
        Send a workflow notification.

        Args:
            db: Database connection
            notification_type: Type of notification (see NotificationType)
            user_id: User to notify
            data: Template data (reference, workflow_name, etc.)
            channels: List of channels (email, sms, push) or None for defaults
            language: Notification language (es, fr)

        Returns:
            bool: True if at least one channel succeeded
        """
        # Get user info
        user_query = """
            SELECT email, phone, full_name, notification_preferences
            FROM users
            WHERE id = $1
        """
        user = await db.fetchrow(user_query, user_id)

        if not user:
            logger.error(f"User not found: {user_id}")
            return False

        # Determine channels
        if channels is None:
            channels = [NotificationChannel.EMAIL]
            # TODO: Check user preferences for SMS/Push

        # Get template
        template = self._templates.get(notification_type)
        if not template:
            logger.error(f"Unknown notification type: {notification_type}")
            return False

        # Add common data
        data["user_name"] = user["full_name"] or user["email"].split("@")[0]
        data["date"] = datetime.now().strftime("%d/%m/%Y %H:%M")

        success = False

        # Send via each channel
        for channel in channels:
            try:
                if channel == NotificationChannel.EMAIL:
                    sent = await self._send_email_notification(
                        user["email"],
                        template,
                        data,
                        language
                    )
                    success = success or sent

                elif channel == NotificationChannel.SMS and user["phone"]:
                    sent = await self._send_sms_notification(
                        user["phone"],
                        template,
                        data,
                        language
                    )
                    success = success or sent

                elif channel == NotificationChannel.PUSH:
                    # TODO: Implement push notifications
                    pass

            except Exception as e:
                logger.exception(f"Error sending {channel} notification: {e}")

        # Log notification
        await self._log_notification(db, user_id, notification_type, channels, success, data)

        return success

    async def _send_email_notification(
        self,
        email: str,
        template: Dict[str, str],
        data: Dict[str, Any],
        language: str
    ) -> bool:
        """Send email notification."""
        subject = template.get(f"subject_{language}", template.get("subject_es", ""))
        body = template.get(f"body_{language}", template.get("body_es", ""))

        # Format template with data
        try:
            subject = subject.format(**data)
            body = body.format(**data)
        except KeyError as e:
            logger.warning(f"Missing template variable: {e}")

        return self.communication_service.send_communication(
            channel=CommunicationType.EMAIL,
            recipient=email,
            subject=subject,
            content=body
        )

    async def _send_sms_notification(
        self,
        phone: str,
        template: Dict[str, str],
        data: Dict[str, Any],
        language: str
    ) -> bool:
        """Send SMS notification."""
        sms_text = template.get(f"sms_{language}", template.get("sms_es", ""))

        # Format template with data
        try:
            sms_text = sms_text.format(**data)
        except KeyError as e:
            logger.warning(f"Missing template variable: {e}")

        # Truncate to SMS limit
        if len(sms_text) > 160:
            sms_text = sms_text[:157] + "..."

        return self.communication_service.send_communication(
            channel=CommunicationType.SMS,
            recipient=phone,
            subject=None,
            content=sms_text
        )

    async def _log_notification(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        notification_type: str,
        channels: List[str],
        success: bool,
        data: Dict[str, Any]
    ) -> None:
        """Log notification in database."""
        try:
            query = """
                INSERT INTO notification_log
                (user_id, notification_type, channels, success, metadata, created_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
            """
            await db.execute(
                query,
                user_id,
                notification_type,
                channels,
                success,
                data
            )
        except Exception as e:
            logger.warning(f"Failed to log notification: {e}")

    # === Convenience Methods ===

    async def notify_request_submitted(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        reference: str,
        workflow_name: str,
        language: str = "es"
    ) -> bool:
        """Send request submitted notification."""
        return await self.send_notification(
            db,
            NotificationType.REQUEST_SUBMITTED,
            user_id,
            {"reference": reference, "workflow_name": workflow_name},
            language=language
        )

    async def notify_request_approved(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        reference: str,
        workflow_name: str,
        next_steps: str = "",
        language: str = "es"
    ) -> bool:
        """Send request approved notification."""
        return await self.send_notification(
            db,
            NotificationType.REQUEST_APPROVED,
            user_id,
            {
                "reference": reference,
                "workflow_name": workflow_name,
                "next_steps": next_steps
            },
            language=language
        )

    async def notify_request_rejected(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        reference: str,
        workflow_name: str,
        rejection_reason: str,
        language: str = "es"
    ) -> bool:
        """Send request rejected notification."""
        return await self.send_notification(
            db,
            NotificationType.REQUEST_REJECTED,
            user_id,
            {
                "reference": reference,
                "workflow_name": workflow_name,
                "rejection_reason": rejection_reason
            },
            language=language
        )

    async def notify_documents_required(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        reference: str,
        workflow_name: str,
        documents: List[str],
        language: str = "es"
    ) -> bool:
        """Send documents required notification."""
        docs_html = "".join([f"<li>{doc}</li>" for doc in documents])
        return await self.send_notification(
            db,
            NotificationType.DOCUMENTS_REQUIRED,
            user_id,
            {
                "reference": reference,
                "workflow_name": workflow_name,
                "documents_list": docs_html
            },
            language=language
        )

    async def notify_payment_pending(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        reference: str,
        workflow_name: str,
        amount: int,
        language: str = "es"
    ) -> bool:
        """Send payment pending notification."""
        return await self.send_notification(
            db,
            NotificationType.PAYMENT_PENDING,
            user_id,
            {
                "reference": reference,
                "workflow_name": workflow_name,
                "amount": f"{amount:,}".replace(",", " ")
            },
            language=language
        )

    async def notify_payment_confirmed(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        reference: str,
        workflow_name: str,
        amount: int,
        transaction_id: str,
        language: str = "es"
    ) -> bool:
        """Send payment confirmed notification."""
        return await self.send_notification(
            db,
            NotificationType.PAYMENT_CONFIRMED,
            user_id,
            {
                "reference": reference,
                "workflow_name": workflow_name,
                "amount": f"{amount:,}".replace(",", " "),
                "transaction_id": transaction_id
            },
            language=language
        )

    async def notify_appointment_scheduled(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        reference: str,
        workflow_name: str,
        appointment_date: str,
        appointment_time: str,
        appointment_location: str,
        documents_to_bring: List[str],
        language: str = "es"
    ) -> bool:
        """Send appointment scheduled notification."""
        docs_html = "".join([f"<li>{doc}</li>" for doc in documents_to_bring])
        return await self.send_notification(
            db,
            NotificationType.APPOINTMENT_SCHEDULED,
            user_id,
            {
                "reference": reference,
                "workflow_name": workflow_name,
                "appointment_date": appointment_date,
                "appointment_time": appointment_time,
                "appointment_location": appointment_location,
                "documents_to_bring": docs_html
            },
            channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
            language=language
        )

    async def notify_request_completed(
        self,
        db: asyncpg.Connection,
        user_id: UUID,
        reference: str,
        workflow_name: str,
        completion_message: str = "",
        language: str = "es"
    ) -> bool:
        """Send request completed notification."""
        return await self.send_notification(
            db,
            NotificationType.REQUEST_COMPLETED,
            user_id,
            {
                "reference": reference,
                "workflow_name": workflow_name,
                "completion_message": completion_message
            },
            language=language
        )


# Singleton instance
workflow_notification_service = WorkflowNotificationService()
