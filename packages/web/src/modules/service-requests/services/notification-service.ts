/**
 * Notification Service for Service Requests
 *
 * Handles sending SMS and Email notifications for service request events:
 * - Appointment confirmation
 * - Payment confirmation
 * - Document validation alerts
 */

import apiClient from '@/core/api/client'

const COMMUNICATIONS_BASE = '/communications'

// =============================================================================
// TYPES
// =============================================================================

export interface SendEmailRequest {
  templateCode: string
  toEmail: string
  variables?: Record<string, unknown>
  language?: 'es' | 'fr' | 'en'
}

export interface SendSmsRequest {
  templateCode: string
  toPhone: string
  variables?: Record<string, unknown>
  language?: 'es' | 'fr' | 'en'
}

export interface NotifyUserSmsRequest {
  userEmail: string
  templateCode: string
  variables?: Record<string, unknown>
}

export interface NotificationResponse {
  success: boolean
  message: string
  messageId?: string
}

// =============================================================================
// NOTIFICATION SERVICE CLASS
// =============================================================================

class NotificationService {
  /**
   * Send email with template
   */
  async sendEmail(request: SendEmailRequest): Promise<NotificationResponse> {
    const response = await apiClient.post<NotificationResponse>(
      `${COMMUNICATIONS_BASE}/email/send-with-template`,
      {
        template_code: request.templateCode,
        to_email: request.toEmail,
        variables: request.variables,
        language: request.language || 'es',
      }
    )
    return response.data
  }

  /**
   * Send SMS with template
   */
  async sendSms(request: SendSmsRequest): Promise<NotificationResponse> {
    const response = await apiClient.post<NotificationResponse>(
      `${COMMUNICATIONS_BASE}/sms/send-with-template`,
      {
        template_code: request.templateCode,
        to_phone: request.toPhone,
        variables: request.variables,
        language: request.language || 'es',
      }
    )
    return response.data
  }

  /**
   * Notify user via SMS using their profile phone number
   */
  async notifyUserSms(request: NotifyUserSmsRequest): Promise<NotificationResponse> {
    const response = await apiClient.post<NotificationResponse>(
      `${COMMUNICATIONS_BASE}/sms/notify-user`,
      {
        user_email: request.userEmail,
        template_code: request.templateCode,
        variables: request.variables,
      }
    )
    return response.data
  }

  // ===========================================================================
  // CONVENIENCE METHODS FOR SERVICE REQUEST EVENTS
  // ===========================================================================

  /**
   * Send appointment confirmation notification (Email + SMS)
   */
  async sendAppointmentConfirmation(params: {
    userEmail: string
    userPhone?: string
    userName: string
    requestReference: string
    locationName: string
    appointmentDate: string
    appointmentTime: string
    language?: 'es' | 'fr' | 'en'
  }): Promise<{ email: boolean; sms: boolean }> {
    const { userEmail, userPhone, userName, requestReference, locationName, appointmentDate, appointmentTime, language = 'es' } = params

    const variables = {
      user_name: userName,
      request_reference: requestReference,
      location_name: locationName,
      appointment_date: appointmentDate,
      appointment_time: appointmentTime,
    }

    const results = { email: false, sms: false }

    // Send email
    try {
      const emailResult = await this.sendEmail({
        templateCode: 'APPOINTMENT_CONFIRMED',
        toEmail: userEmail,
        variables,
        language,
      })
      results.email = emailResult.success
    } catch (error) {
      console.error('Failed to send appointment email:', error)
    }

    // Send SMS if phone provided
    if (userPhone) {
      try {
        const smsResult = await this.sendSms({
          templateCode: 'APPOINTMENT_CONFIRMED',
          toPhone: userPhone,
          variables,
          language,
        })
        results.sms = smsResult.success
      } catch (error) {
        console.error('Failed to send appointment SMS:', error)
      }
    }

    return results
  }

  /**
   * Send payment confirmation notification (Email + SMS)
   */
  async sendPaymentConfirmation(params: {
    userEmail: string
    userPhone?: string
    userName: string
    requestReference: string
    amount: number
    currency: string
    paymentMethod: string
    language?: 'es' | 'fr' | 'en'
  }): Promise<{ email: boolean; sms: boolean }> {
    const { userEmail, userPhone, userName, requestReference, amount, currency, paymentMethod, language = 'es' } = params

    const variables = {
      user_name: userName,
      request_reference: requestReference,
      amount: amount.toLocaleString(),
      currency,
      payment_method: paymentMethod,
    }

    const results = { email: false, sms: false }

    // Send email
    try {
      const emailResult = await this.sendEmail({
        templateCode: 'PAYMENT_RECEIVED',
        toEmail: userEmail,
        variables,
        language,
      })
      results.email = emailResult.success
    } catch (error) {
      console.error('Failed to send payment email:', error)
    }

    // Send SMS if phone provided
    if (userPhone) {
      try {
        const smsResult = await this.sendSms({
          templateCode: 'PAYMENT_RECEIVED',
          toPhone: userPhone,
          variables,
          language,
        })
        results.sms = smsResult.success
      } catch (error) {
        console.error('Failed to send payment SMS:', error)
      }
    }

    return results
  }

  /**
   * Send document validation alert (low confidence)
   */
  async sendDocumentValidationAlert(params: {
    userEmail: string
    userName: string
    requestReference: string
    documentName: string
    confidence: number
    issues: string[]
    language?: 'es' | 'fr' | 'en'
  }): Promise<boolean> {
    const { userEmail, userName, requestReference, documentName, confidence, issues, language = 'es' } = params

    try {
      const result = await this.sendEmail({
        templateCode: 'DOCUMENT_VALIDATION_ALERT',
        toEmail: userEmail,
        variables: {
          user_name: userName,
          request_reference: requestReference,
          document_name: documentName,
          confidence: Math.round(confidence * 100),
          issues: issues.join(', '),
        },
        language,
      })
      return result.success
    } catch (error) {
      console.error('Failed to send document validation alert:', error)
      return false
    }
  }

  /**
   * Send request submission confirmation
   */
  async sendSubmissionConfirmation(params: {
    userEmail: string
    userPhone?: string
    userName: string
    requestReference: string
    serviceName: string
    language?: 'es' | 'fr' | 'en'
  }): Promise<{ email: boolean; sms: boolean }> {
    const { userEmail, userPhone, userName, requestReference, serviceName, language = 'es' } = params

    const variables = {
      user_name: userName,
      request_reference: requestReference,
      service_name: serviceName,
    }

    const results = { email: false, sms: false }

    // Send email
    try {
      const emailResult = await this.sendEmail({
        templateCode: 'REQUEST_SUBMITTED',
        toEmail: userEmail,
        variables,
        language,
      })
      results.email = emailResult.success
    } catch (error) {
      console.error('Failed to send submission email:', error)
    }

    // Send SMS if phone provided
    if (userPhone) {
      try {
        const smsResult = await this.sendSms({
          templateCode: 'REQUEST_SUBMITTED',
          toPhone: userPhone,
          variables,
          language,
        })
        results.sms = smsResult.success
      } catch (error) {
        console.error('Failed to send submission SMS:', error)
      }
    }

    return results
  }
}

// Singleton export
export const notificationService = new NotificationService()
export default notificationService
