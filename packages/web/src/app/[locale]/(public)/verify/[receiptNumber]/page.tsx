'use client';

/**
 * Verification Page - Dual mode
 *
 * Handles both:
 * - Service Request verification: /verify/SRV-2026-00011 (from PDF QR code)
 * - Payment Receipt verification: /verify/REC-2026-000001?t={hmac_token}
 *
 * Auto-detects the type by prefix and calls the appropriate API endpoint.
 */

import { useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { useLocale } from 'next-intl';
import {
  CheckCircle, XCircle, Loader2, Shield, FileText,
  Calendar, CreditCard, User, Building2, AlertTriangle,
  Clock, MapPin,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';

// ================================================================
// Types
// ================================================================

interface ReceiptResult {
  verification_type: 'receipt';
  valid: boolean;
  receipt_number: string;
  message: string;
  payment_date?: string;
  amount?: number;
  currency?: string;
  payment_method?: string;
  payer_name?: string;
  workflow_code?: string;
  entity_code?: string;
  solicitud_type?: string;
  service_request_reference?: string;
  validated_by?: string;
  validated_at?: string;
}

interface ServiceRequestResult {
  verification_type: 'service_request';
  valid: boolean;
  reference: string;
  message: string;
  workflow_name?: string;
  solicitud_type?: string;
  entity_code?: string;
  status?: string;
  status_label?: string;
  created_at?: string;
  appointment_date?: string;
  appointment_time?: string;
  appointment_location?: string;
  payment_status?: string;
  payment_amount?: number;
  currency?: string;
}

interface LicenseResult {
  verification_type: 'license';
  valid: boolean;
  license_ref: string;
  message: string;
  company_name?: string;
  nif?: string;
  regimen_fiscal?: string;
  bundle_name?: string;
  commerce_type?: string;
  fiscal_year?: number;
  status?: string;
  total_amount?: number;
  amount_paid?: number;
  obligations_total?: number;
  obligations_paid?: number;
  compliance_score?: number;
  currency?: string;
}

type VerificationResult = ReceiptResult | ServiceRequestResult | LicenseResult;

// ================================================================
// Translations
// ================================================================

const translations = {
  es: {
    // Common
    verifying: 'Verificando...',
    error: 'Error de Verificacion',
    error_message: 'No se pudo verificar. Intente nuevamente.',
    official_notice: 'Este sistema de verificacion es proporcionado por la plataforma Facil para autenticar las solicitudes.',
    // Receipt
    receipt_title: 'Verificacion de Recibo',
    receipt_subtitle: 'Sistema de Verificacion de Pagos del Tesoro Publico',
    valid_receipt: 'Recibo Valido',
    invalid_receipt: 'Recibo No Valido',
    receipt_number: 'Numero de Recibo',
    payment_date: 'Fecha de Pago',
    amount: 'Monto',
    payment_method: 'Metodo de Pago',
    payer: 'Pagador',
    workflow_code: 'Codigo de Tramite',
    entity: 'Entidad',
    request_type: 'Tipo de Solicitud',
    request_reference: 'Referencia de Solicitud',
    validated_by: 'Validado por',
    validation_date: 'Fecha de Validacion',
    missing_token: 'Token de verificacion no proporcionado',
    cash: 'Efectivo',
    check: 'Cheque',
    mobile_money: 'Mobile Money',
    card: 'Tarjeta',
    bank_transfer: 'Transferencia',
    // Service Request
    sr_title: 'Verificacion de Solicitud',
    sr_subtitle: 'Plataforma de Servicios Administrativos',
    valid_request: 'Solicitud Verificada',
    invalid_request: 'Solicitud No Encontrada',
    reference: 'Referencia',
    workflow: 'Tramite',
    status: 'Estado',
    created: 'Fecha de Solicitud',
    appointment: 'Cita Programada',
    appointment_date: 'Fecha',
    appointment_time: 'Hora',
    appointment_location: 'Ubicacion',
    payment_status: 'Estado del Pago',
    payment_pending: 'Pendiente',
    payment_completed: 'Pagado',
    payment_processing: 'En proceso',
    no_appointment: 'Sin cita programada',
    // License
    lic_title: 'Verificacion de Licencia Comercial',
    lic_subtitle: 'Sistema de Verificacion de Licencias — Facil',
    valid_license: 'Licencia Verificada',
    invalid_license: 'Licencia No Valida',
    lic_company: 'Empresa',
    lic_nif: 'NIF',
    lic_regime: 'Regimen Fiscal',
    lic_bundle: 'Paquete',
    lic_commerce: 'Tipo de Comercio',
    lic_fiscal_year: 'Año Fiscal',
    lic_status: 'Estado',
    lic_total: 'Total Obligaciones',
    lic_paid: 'Pagado',
    lic_obligations: 'Obligaciones',
    lic_compliance: 'Cumplimiento',
  },
  fr: {
    verifying: 'Verification en cours...',
    error: 'Erreur de Verification',
    error_message: 'Impossible de verifier. Veuillez reessayer.',
    official_notice: 'Ce systeme de verification est fourni par la plateforme Facil pour authentifier les requetes.',
    receipt_title: 'Verification du Recu',
    receipt_subtitle: 'Systeme de Verification des Paiements du Tresor Public',
    valid_receipt: 'Recu Valide',
    invalid_receipt: 'Recu Non Valide',
    receipt_number: 'Numero de Recu',
    payment_date: 'Date de Paiement',
    amount: 'Montant',
    payment_method: 'Mode de Paiement',
    payer: 'Payeur',
    workflow_code: 'Code de Procedure',
    entity: 'Entite',
    request_type: 'Type de Demande',
    request_reference: 'Reference de Demande',
    validated_by: 'Valide par',
    validation_date: 'Date de Validation',
    missing_token: 'Token de verification non fourni',
    cash: 'Especes',
    check: 'Cheque',
    mobile_money: 'Mobile Money',
    card: 'Carte',
    bank_transfer: 'Virement',
    sr_title: 'Verification de la Demande',
    sr_subtitle: 'Plateforme de Services Administratifs',
    valid_request: 'Demande Verifiee',
    invalid_request: 'Demande Non Trouvee',
    reference: 'Reference',
    workflow: 'Procedure',
    status: 'Statut',
    created: 'Date de Demande',
    appointment: 'Rendez-vous Programme',
    appointment_date: 'Date',
    appointment_time: 'Heure',
    appointment_location: 'Lieu',
    payment_status: 'Statut du Paiement',
    payment_pending: 'En attente',
    payment_completed: 'Paye',
    payment_processing: 'En cours',
    no_appointment: 'Sans rendez-vous programme',
    lic_title: 'Verification de Licence Commerciale',
    lic_subtitle: 'Systeme de Verification des Licences — Facil',
    valid_license: 'Licence Verifiee',
    invalid_license: 'Licence Non Valide',
    lic_company: 'Entreprise',
    lic_nif: 'NIF',
    lic_regime: 'Regime Fiscal',
    lic_bundle: 'Forfait',
    lic_commerce: 'Type de Commerce',
    lic_fiscal_year: 'Annee Fiscale',
    lic_status: 'Statut',
    lic_total: 'Total Obligations',
    lic_paid: 'Paye',
    lic_obligations: 'Obligations',
    lic_compliance: 'Conformite',
  },
  en: {
    verifying: 'Verifying...',
    error: 'Verification Error',
    error_message: 'Could not verify. Please try again.',
    official_notice: 'This verification system is provided by the Facil platform to authenticate requests.',
    receipt_title: 'Receipt Verification',
    receipt_subtitle: 'Public Treasury Payment Verification System',
    valid_receipt: 'Valid Receipt',
    invalid_receipt: 'Invalid Receipt',
    receipt_number: 'Receipt Number',
    payment_date: 'Payment Date',
    amount: 'Amount',
    payment_method: 'Payment Method',
    payer: 'Payer',
    workflow_code: 'Procedure Code',
    entity: 'Entity',
    request_type: 'Request Type',
    request_reference: 'Request Reference',
    validated_by: 'Validated by',
    validation_date: 'Validation Date',
    missing_token: 'Verification token not provided',
    cash: 'Cash',
    check: 'Check',
    mobile_money: 'Mobile Money',
    card: 'Card',
    bank_transfer: 'Bank Transfer',
    sr_title: 'Request Verification',
    sr_subtitle: 'Administrative Services Platform',
    valid_request: 'Request Verified',
    invalid_request: 'Request Not Found',
    reference: 'Reference',
    workflow: 'Procedure',
    status: 'Status',
    created: 'Request Date',
    appointment: 'Scheduled Appointment',
    appointment_date: 'Date',
    appointment_time: 'Time',
    appointment_location: 'Location',
    payment_status: 'Payment Status',
    payment_pending: 'Pending',
    payment_completed: 'Paid',
    payment_processing: 'Processing',
    no_appointment: 'No appointment scheduled',
    lic_title: 'Commercial License Verification',
    lic_subtitle: 'License Verification System — Facil',
    valid_license: 'License Verified',
    invalid_license: 'Invalid License',
    lic_company: 'Company',
    lic_nif: 'NIF',
    lic_regime: 'Tax Regime',
    lic_bundle: 'Bundle',
    lic_commerce: 'Commerce Type',
    lic_fiscal_year: 'Fiscal Year',
    lic_status: 'Status',
    lic_total: 'Total Obligations',
    lic_paid: 'Paid',
    lic_obligations: 'Obligations',
    lic_compliance: 'Compliance',
  },
};

// ================================================================
// Helpers
// ================================================================

/**
 * Detect if a reference is a service_request by its prefix.
 * All workflow references use a 3-letter code + year format (e.g. CON-2026-00001).
 * Receipt references use REC- prefix and are handled by the default branch.
 */
const SERVICE_REQUEST_PREFIXES = [
  'SRV-', 'CON-', 'PAS-', 'RES-', 'MAT-', 'INS-', 'DUP-',
  'PRO-', 'CAR-', 'VER-', 'TRA-', 'PER-', 'CER-', 'VIS-',
  'INM-', 'SOL-', 'REG-', 'LIQ-', 'IMP-',
];

function isServiceRequest(ref: string): boolean {
  // Known prefixes
  if (SERVICE_REQUEST_PREFIXES.some(p => ref.startsWith(p))) return true;
  // Fallback: 3 uppercase letters + dash + 4-digit year pattern (not REC-, not LIC-)
  if (/^[A-Z]{3}-\d{4}-/.test(ref) && !ref.startsWith('REC-') && !ref.startsWith('LIC-')) return true;
  return false;
}

function isLicense(ref: string): boolean {
  return ref.startsWith('LIC-');
}

function isCertificate(ref: string): boolean {
  return ref.startsWith('CLC-');
}

function isReceiptResult(result: VerificationResult): result is ReceiptResult {
  return result.verification_type === 'receipt';
}

function isServiceRequestResult(result: VerificationResult): result is ServiceRequestResult {
  return result.verification_type === 'service_request';
}

function isLicenseResult(result: VerificationResult): result is LicenseResult {
  return result.verification_type === 'license';
}

// ================================================================
// Component
// ================================================================

export default function VerifyPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const locale = useLocale() as 'es' | 'fr' | 'en';
  const t = translations[locale] || translations.es;

  const reference = params.receiptNumber as string;
  const token = searchParams.get('t');
  const licenseId = searchParams.get('lid');
  const isSR = isServiceRequest(reference);
  const isLIC = isLicense(reference);
  const isCERT = isCertificate(reference);

  const [loading, setLoading] = useState(true);
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const verify = async () => {
      // All verification types require a token
      if (!token) {
        setError(t.missing_token);
        setLoading(false);
        return;
      }

      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://taxasge-api.emacsah.com';
        let url: string;

        if (isSR) {
          url = `${apiUrl}/api/v1/verify/request/${encodeURIComponent(reference)}?t=${encodeURIComponent(token)}`;
        } else if (isCERT) {
          url = `${apiUrl}/api/v1/verify/certificate/${encodeURIComponent(reference)}?t=${encodeURIComponent(token)}&lid=${encodeURIComponent(licenseId || '')}`;
        } else if (isLIC) {
          url = `${apiUrl}/api/v1/verify/license/${encodeURIComponent(reference)}?t=${encodeURIComponent(token)}&lid=${encodeURIComponent(licenseId || '')}`;
        } else {
          url = `${apiUrl}/api/v1/verify/${encodeURIComponent(reference)}?t=${encodeURIComponent(token)}`;
        }

        const response = await fetch(url);
        if (!response.ok) {
          throw new Error('Verification failed');
        }

        const data: VerificationResult = await response.json();
        setResult(data);
      } catch (err) {
        console.error('Verification error:', err);
        setError(t.error_message);
      } finally {
        setLoading(false);
      }
    };

    verify();
  }, [reference, token, isSR, isLIC, isCERT, licenseId, t]);

  const getPaymentMethodLabel = (method?: string): string => {
    if (!method) return '-';
    const methodMap: Record<string, keyof typeof t> = {
      cash: 'cash',
      check: 'check',
      mobile_money: 'mobile_money',
      card: 'card',
      bank_transfer: 'bank_transfer',
    };
    const key = methodMap[method];
    return key ? (t[key] as string) : method;
  };

  const formatAmount = (amount?: number, currency?: string): string => {
    if (!amount) return '-';
    return `${amount.toLocaleString()} ${currency || 'XAF'}`;
  };

  const getPaymentStatusLabel = (status?: string): string => {
    if (!status) return '-';
    const map: Record<string, keyof typeof t> = {
      completed: 'payment_completed',
      pending: 'payment_pending',
      pending_agent_review: 'payment_pending',
      submitted: 'payment_pending',
      processing: 'payment_processing',
    };
    const key = map[status];
    return key ? (t[key] as string) : status;
  };

  // Title/subtitle based on type
  const title = isLIC ? t.lic_title : isSR ? t.sr_title : t.receipt_title;
  const subtitle = isLIC ? t.lic_subtitle : isSR ? t.sr_subtitle : t.receipt_subtitle;

  // ================================================================
  // Loading
  // ================================================================
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-blue-50 to-white">
        <Card className="w-full max-w-md mx-4">
          <CardContent className="pt-8 pb-8">
            <div className="flex flex-col items-center space-y-4">
              <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
              <p className="text-lg font-medium text-gray-700">{t.verifying}</p>
              <p className="text-sm text-gray-500 font-mono">{reference}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ================================================================
  // Error
  // ================================================================
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-red-50 to-white p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="mx-auto mb-4 h-16 w-16 rounded-full bg-red-100 flex items-center justify-center">
              <AlertTriangle className="h-8 w-8 text-red-600" />
            </div>
            <CardTitle className="text-xl text-red-700">{t.error}</CardTitle>
          </CardHeader>
          <CardContent className="text-center">
            <p className="text-gray-600">{error}</p>
            <p className="mt-4 font-mono text-sm text-gray-400">{reference}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!result) return null;

  // ================================================================
  // Service Request Result
  // ================================================================
  if (isServiceRequestResult(result)) {
    return (
      <div className={`min-h-screen py-8 px-4 ${result.valid ? 'bg-gradient-to-b from-green-50 to-white' : 'bg-gradient-to-b from-orange-50 to-white'}`}>
        <div className="max-w-lg mx-auto">
          {/* Header */}
          <div className="text-center mb-6">
            <div className="flex justify-center mb-4">
              <Shield className="h-12 w-12 text-green-700" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
            <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
          </div>

          {/* Status Badge */}
          <Card className={`mb-6 ${result.valid ? 'border-green-200' : 'border-orange-200'}`}>
            <CardContent className="pt-6">
              <div className="flex flex-col items-center space-y-4">
                {result.valid ? (
                  <div className="h-20 w-20 rounded-full bg-green-100 flex items-center justify-center">
                    <CheckCircle className="h-12 w-12 text-green-600" />
                  </div>
                ) : (
                  <div className="h-20 w-20 rounded-full bg-orange-100 flex items-center justify-center">
                    <XCircle className="h-12 w-12 text-orange-600" />
                  </div>
                )}
                <Badge
                  variant={result.valid ? 'default' : 'destructive'}
                  className={`text-lg px-4 py-2 ${result.valid ? 'bg-green-600' : 'bg-orange-600'}`}
                >
                  {result.valid ? t.valid_request : t.invalid_request}
                </Badge>
                <p className="text-sm text-gray-500">{result.message}</p>
              </div>
            </CardContent>
          </Card>

          {/* Details */}
          {result.valid && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <FileText className="h-5 w-5" />
                  {t.reference}: {result.reference}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Workflow + Status */}
                <div className="grid grid-cols-2 gap-4">
                  {result.workflow_name && (
                    <div>
                      <p className="text-xs text-gray-500 uppercase">{t.workflow}</p>
                      <p className="font-medium">{result.workflow_name}</p>
                    </div>
                  )}
                  {result.status_label && (
                    <div>
                      <p className="text-xs text-gray-500 uppercase">{t.status}</p>
                      <Badge variant="outline" className="mt-1">{result.status_label}</Badge>
                    </div>
                  )}
                </div>

                <Separator />

                {/* Solicitud type + Date */}
                <div className="grid grid-cols-2 gap-4">
                  {result.solicitud_type && (
                    <div>
                      <p className="text-xs text-gray-500 uppercase">{t.request_type}</p>
                      <p className="font-medium capitalize">{result.solicitud_type}</p>
                    </div>
                  )}
                  {result.created_at && (
                    <div>
                      <p className="text-xs text-gray-500 uppercase">{t.created}</p>
                      <p className="font-medium flex items-center gap-1">
                        <Calendar className="h-4 w-4 text-gray-400" />
                        {result.created_at}
                      </p>
                    </div>
                  )}
                </div>

                {result.entity_code && (
                  <div>
                    <p className="text-xs text-gray-500 uppercase">{t.entity}</p>
                    <p className="font-medium flex items-center gap-1">
                      <Building2 className="h-4 w-4 text-gray-400" />
                      {result.entity_code}
                    </p>
                  </div>
                )}

                {/* Appointment */}
                {result.appointment_date && (
                  <>
                    <Separator />
                    <div className="bg-blue-50 rounded-lg p-3">
                      <p className="text-xs text-gray-500 uppercase mb-2">{t.appointment}</p>
                      <div className="grid grid-cols-3 gap-2">
                        <div>
                          <p className="text-xs text-gray-400">{t.appointment_date}</p>
                          <p className="font-medium flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            {result.appointment_date}
                          </p>
                        </div>
                        {result.appointment_time && (
                          <div>
                            <p className="text-xs text-gray-400">{t.appointment_time}</p>
                            <p className="font-medium flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {result.appointment_time}
                            </p>
                          </div>
                        )}
                        {result.appointment_location && (
                          <div>
                            <p className="text-xs text-gray-400">{t.appointment_location}</p>
                            <p className="font-medium flex items-center gap-1">
                              <MapPin className="h-3 w-3" />
                              {result.appointment_location}
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  </>
                )}

                {/* Payment */}
                {(result.payment_amount || result.payment_status) && (
                  <>
                    <Separator />
                    <div className="grid grid-cols-2 gap-4">
                      {result.payment_amount && (
                        <div>
                          <p className="text-xs text-gray-500 uppercase">{t.amount}</p>
                          <p className="font-bold text-lg text-green-700">
                            {formatAmount(result.payment_amount, result.currency)}
                          </p>
                        </div>
                      )}
                      {result.payment_status && (
                        <div>
                          <p className="text-xs text-gray-500 uppercase">{t.payment_status}</p>
                          <p className="font-medium">{getPaymentStatusLabel(result.payment_status)}</p>
                        </div>
                      )}
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          )}

          <p className="mt-6 text-xs text-center text-gray-400 px-4">
            {t.official_notice}
          </p>
        </div>
      </div>
    );
  }

  // ================================================================
  // License Result
  // ================================================================
  if (isLicenseResult(result)) {
    const statusColors: Record<string, string> = {
      open: 'bg-blue-100 text-blue-800',
      partial: 'bg-yellow-100 text-yellow-800',
      complete: 'bg-green-100 text-green-800',
      overdue: 'bg-red-100 text-red-800',
      closed: 'bg-gray-100 text-gray-800',
    };
    return (
      <div className={`min-h-screen py-8 px-4 ${result.valid ? 'bg-gradient-to-b from-green-50 to-white' : 'bg-gradient-to-b from-orange-50 to-white'}`}>
        <div className="max-w-lg mx-auto">
          <div className="text-center mb-6">
            <div className="flex justify-center mb-4">
              <Shield className="h-12 w-12 text-green-700" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
            <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
          </div>

          <Card className={`mb-6 ${result.valid ? 'border-green-200' : 'border-orange-200'}`}>
            <CardContent className="pt-6">
              <div className="flex flex-col items-center space-y-4">
                {result.valid ? (
                  <div className="h-20 w-20 rounded-full bg-green-100 flex items-center justify-center">
                    <CheckCircle className="h-12 w-12 text-green-600" />
                  </div>
                ) : (
                  <div className="h-20 w-20 rounded-full bg-orange-100 flex items-center justify-center">
                    <XCircle className="h-12 w-12 text-orange-600" />
                  </div>
                )}
                <Badge
                  variant={result.valid ? 'default' : 'destructive'}
                  className={`text-lg px-4 py-2 ${result.valid ? 'bg-green-600' : 'bg-orange-600'}`}
                >
                  {result.valid ? t.valid_license : t.invalid_license}
                </Badge>
                <p className="font-mono text-sm text-gray-500">{result.license_ref}</p>
              </div>
            </CardContent>
          </Card>

          {result.valid && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Building2 className="h-5 w-5" />
                  {result.company_name}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  {result.nif && (
                    <div>
                      <p className="text-xs text-gray-500 uppercase">{t.lic_nif}</p>
                      <p className="font-mono font-medium">{result.nif}</p>
                    </div>
                  )}
                  {result.fiscal_year && (
                    <div>
                      <p className="text-xs text-gray-500 uppercase">{t.lic_fiscal_year}</p>
                      <p className="font-medium">{result.fiscal_year}</p>
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {result.regimen_fiscal && (
                    <div>
                      <p className="text-xs text-gray-500 uppercase">{t.lic_regime}</p>
                      <Badge variant="outline" className="mt-1 capitalize">{result.regimen_fiscal}</Badge>
                    </div>
                  )}
                  {result.status && (
                    <div>
                      <p className="text-xs text-gray-500 uppercase">{t.lic_status}</p>
                      <Badge className={`mt-1 ${statusColors[result.status] || 'bg-gray-100 text-gray-800'}`}>
                        {result.status.toUpperCase()}
                      </Badge>
                    </div>
                  )}
                </div>

                {result.bundle_name && (
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs text-gray-500 uppercase">{t.lic_bundle}</p>
                      <p className="font-medium">{result.bundle_name}</p>
                    </div>
                    {result.commerce_type && (
                      <div>
                        <p className="text-xs text-gray-500 uppercase">{t.lic_commerce}</p>
                        <p className="font-medium capitalize">{result.commerce_type}</p>
                      </div>
                    )}
                  </div>
                )}

                <Separator />

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-gray-500 uppercase">{t.lic_total}</p>
                    <p className="font-bold text-lg">{formatAmount(result.total_amount, result.currency)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase">{t.lic_paid}</p>
                    <p className="font-bold text-lg text-green-700">{formatAmount(result.amount_paid, result.currency)}</p>
                  </div>
                </div>

                {(result.obligations_total !== undefined) && (
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs text-gray-500 uppercase">{t.lic_obligations}</p>
                      <p className="font-medium">{result.obligations_paid}/{result.obligations_total}</p>
                    </div>
                    {result.compliance_score !== undefined && result.compliance_score !== null && (
                      <div>
                        <p className="text-xs text-gray-500 uppercase">{t.lic_compliance}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                            <div className="h-full bg-green-500 rounded-full" style={{ width: `${result.compliance_score}%` }} />
                          </div>
                          <span className="text-sm font-medium">{result.compliance_score}%</span>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          <p className="mt-6 text-xs text-center text-gray-400 px-4">
            {t.official_notice}
          </p>
        </div>
      </div>
    );
  }

  // ================================================================
  // Receipt Result (existing behavior)
  // ================================================================
  if (isReceiptResult(result)) {
    return (
      <div className={`min-h-screen py-8 px-4 ${result.valid ? 'bg-gradient-to-b from-green-50 to-white' : 'bg-gradient-to-b from-orange-50 to-white'}`}>
        <div className="max-w-lg mx-auto">
          {/* Header */}
          <div className="text-center mb-6">
            <div className="flex justify-center mb-4">
              <Shield className="h-12 w-12 text-blue-600" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
            <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
          </div>

          {/* Status Card */}
          <Card className={`mb-6 ${result.valid ? 'border-green-200' : 'border-orange-200'}`}>
            <CardContent className="pt-6">
              <div className="flex flex-col items-center space-y-4">
                {result.valid ? (
                  <div className="h-20 w-20 rounded-full bg-green-100 flex items-center justify-center">
                    <CheckCircle className="h-12 w-12 text-green-600" />
                  </div>
                ) : (
                  <div className="h-20 w-20 rounded-full bg-orange-100 flex items-center justify-center">
                    <XCircle className="h-12 w-12 text-orange-600" />
                  </div>
                )}
                <Badge
                  variant={result.valid ? 'default' : 'destructive'}
                  className={`text-lg px-4 py-2 ${result.valid ? 'bg-green-600' : 'bg-orange-600'}`}
                >
                  {result.valid ? t.valid_receipt : t.invalid_receipt}
                </Badge>
                <p className="text-sm text-gray-500">{result.message}</p>
              </div>
            </CardContent>
          </Card>

          {/* Receipt Details */}
          {result.valid && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <FileText className="h-5 w-5" />
                  {t.receipt_number}: {result.receipt_number}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-gray-500 uppercase">{t.payment_date}</p>
                    <p className="font-medium flex items-center gap-1">
                      <Calendar className="h-4 w-4 text-gray-400" />
                      {result.payment_date || '-'}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase">{t.amount}</p>
                    <p className="font-bold text-lg text-green-700">
                      {formatAmount(result.amount, result.currency)}
                    </p>
                  </div>
                </div>

                <Separator />

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-gray-500 uppercase">{t.payment_method}</p>
                    <p className="font-medium flex items-center gap-1">
                      <CreditCard className="h-4 w-4 text-gray-400" />
                      {getPaymentMethodLabel(result.payment_method)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase">{t.payer}</p>
                    <p className="font-medium flex items-center gap-1">
                      <User className="h-4 w-4 text-gray-400" />
                      {result.payer_name || '-'}
                    </p>
                  </div>
                </div>

                <Separator />

                <div className="space-y-3">
                  {result.workflow_code && (
                    <div>
                      <p className="text-xs text-gray-500 uppercase">{t.workflow_code}</p>
                      <p className="font-mono font-medium">{result.workflow_code}</p>
                    </div>
                  )}
                  {result.entity_code && (
                    <div>
                      <p className="text-xs text-gray-500 uppercase">{t.entity}</p>
                      <p className="font-medium flex items-center gap-1">
                        <Building2 className="h-4 w-4 text-gray-400" />
                        {result.entity_code}
                      </p>
                    </div>
                  )}
                  {result.solicitud_type && (
                    <div>
                      <p className="text-xs text-gray-500 uppercase">{t.request_type}</p>
                      <p className="font-medium">{result.solicitud_type}</p>
                    </div>
                  )}
                  {result.service_request_reference && (
                    <div>
                      <p className="text-xs text-gray-500 uppercase">{t.request_reference}</p>
                      <p className="font-mono text-sm">{result.service_request_reference}</p>
                    </div>
                  )}
                </div>

                {result.validated_by && (
                  <>
                    <Separator />
                    <div className="bg-green-50 rounded-lg p-3">
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <p className="text-xs text-gray-500 uppercase">{t.validated_by}</p>
                          <p className="font-medium text-sm">{result.validated_by}</p>
                        </div>
                        {result.validated_at && (
                          <div>
                            <p className="text-xs text-gray-500 uppercase">{t.validation_date}</p>
                            <p className="font-medium text-sm">{result.validated_at}</p>
                          </div>
                        )}
                      </div>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          )}

          <p className="mt-6 text-xs text-center text-gray-400 px-4">
            {t.official_notice}
          </p>
        </div>
      </div>
    );
  }

  return null;
}
