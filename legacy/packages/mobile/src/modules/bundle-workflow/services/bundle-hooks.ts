/**
 * useBundleWizard — aligned with web useBundleWizard.ts
 *
 * 6-step wizard: Company → Upload → Classification → Obligations → Payment → Confirmation
 * Existing company: skips Upload+Classification → direct to Obligations
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { Linking } from 'react-native';
import * as bundleApi from './bundle-api';
import * as wizardApi from '@modules/wizard/services/wizard-api';
import type {
  CompanySummary,
  MyCompanyWithStatus,
  CompanySearchResult,
  BundleInitiateResponse,
  BundlePaymentResult,
  ClassifyPreviewResponse,
  DocumentPreview,
  ProcessingMode,
  PaymentMethod,
} from '../types';

/**
 * Document code expected by the backend for the bundle company evidence
 * (certificado de empadronamiento / business registration). Aligned with the web flow.
 */
const BUNDLE_COMPANY_DOCUMENT_CODE = 'certificado_padron';

interface UseBundleWizardOptions {
  /** Optional company UUID to auto-select on mount (deep-link from "Mes Empresas"). */
  preselectCompanyId?: string | null;
}

export function useBundleWizard(options: UseBundleWizardOptions = {}) {
  const { preselectCompanyId } = options;
  const [currentStep, setCurrentStep] = useState(0);
  const totalSteps = 6;
  const preselectAppliedRef = useRef(false);

  // Step 0: Company
  const [myCompanies, setMyCompanies] = useState<MyCompanyWithStatus[]>([]);
  const [searchResults, setSearchResults] = useState<CompanySearchResult[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<CompanySummary | null>(null);
  const [companyExists, setCompanyExists] = useState(true);
  const [isLoadingCompanies, setIsLoadingCompanies] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const searchDebounceRef = useRef<NodeJS.Timeout>(null);
  const searchSeqRef = useRef(0);

  // Step 1: Document upload (requires a wizard session — same flow as web).
  // Backend rejects /wizard-sessions/preview-document (no such route); the correct
  // endpoint is POST /wizard-sessions/{sessionId}/documents/preview?document_code=...
  // We create a BUNDLE_PAYMENT wizard session before the first upload (TTL 30min Redis).
  const [wizardSessionId, setWizardSessionId] = useState<string | null>(null);
  const [documentPreview, setDocumentPreview] = useState<DocumentPreview | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  // Step 2: Classification — all editable fields (aligned with web EditableCompanyFields)
  const [classificationPreview, setClassificationPreview] = useState<ClassifyPreviewResponse | null>(null);
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);
  const [selectedCommerceType, setSelectedCommerceType] = useState<string | null>(null);
  // 8 editable fields — aligned with web `EditableCompanyFields`
  // (`packages/web/src/modules/bundle-workflow/hooks/useBundleWizard.ts:37-46`).
  // NIF must be editable so the citizen can correct OCR misreads — without it
  // an unverifiable certificate would block company creation in mobile only.
  const [editedFields, setEditedFieldsState] = useState<Record<string, string | null>>({
    legalName: null, registrationNumber: null, nif: null, localidad: null,
    provincia: null, sector: null, objetoSocial: null, formaJuridica: null,
  });
  const setEditedField = useCallback((key: string, value: string | null) => {
    setEditedFieldsState((prev) => ({ ...prev, [key]: value }));
  }, []);

  // Step 3: Obligations
  const [licenseData, setLicenseData] = useState<BundleInitiateResponse | null>(null);
  const [selectedMode, setSelectedModeState] = useState<ProcessingMode>('consolidated');
  const [selectedObligationIds, setSelectedObligationIds] = useState<Set<string>>(new Set());
  const [isInitiating, setIsInitiating] = useState(false);

  // Step 4: Payment
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod | null>(null);
  const [phoneNumber, setPhoneNumber] = useState('');
  const [isPaymentProcessing, setIsPaymentProcessing] = useState(false);
  const paymentLockRef = useRef(false);

  // Step 5: Confirmation
  const [paymentResult, setPaymentResult] = useState<BundlePaymentResult | null>(null);

  // Global
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // ── Step 0: Company ──

  const loadMyCompanies = useCallback(async () => {
    setIsLoadingCompanies(true);
    try {
      const data = await bundleApi.getMyCompanies();
      setMyCompanies(data.companies || []);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.response?.data?.message_es || 'Failed to load companies');
    } finally { setIsLoadingCompanies(false); }
  }, []);

  useEffect(() => { loadMyCompanies(); }, [loadMyCompanies]);

  // Auto-select company when arriving from "Mes Empresas / Pagar obligaciones".
  // Runs once after myCompanies loads — guards against re-runs (would clobber
  // user's manual selection on step 0).
  // Note: MyCompanyWithStatus.company is already CompanySummary (see types/),
  // backend /my-companies returns the same field set. No cast needed.
  useEffect(() => {
    if (preselectAppliedRef.current) return;
    if (!preselectCompanyId) return;
    if (myCompanies.length === 0) return;
    const match = myCompanies.find((mc) => mc.company.id === preselectCompanyId);
    if (!match) return;
    preselectAppliedRef.current = true;
    setSelectedCompany(match.company);
    setCompanyExists(true);
  }, [preselectCompanyId, myCompanies]);

  const searchCompany = useCallback((q: string) => {
    if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
    if (q.length < 2) { setSearchResults([]); setIsSearching(false); return; }
    setIsSearching(true);
    const seq = ++searchSeqRef.current;
    searchDebounceRef.current = setTimeout(async () => {
      try {
        const data = await bundleApi.searchCompany(q);
        if (seq === searchSeqRef.current) setSearchResults(data.companies || []);
      } catch { /* stale */ }
      finally { if (seq === searchSeqRef.current) setIsSearching(false); }
    }, 300);
  }, []);

  const selectCompany = useCallback((company: CompanySummary) => {
    setSelectedCompany(company);
    setCompanyExists(true);
    setError(null);
  }, []);

  const clearCompanySelection = useCallback(() => {
    setSelectedCompany(null);
    setCompanyExists(true);
    setLicenseData(null);
    setSearchResults([]);
  }, []);

  const requestNewCompany = useCallback(() => {
    setCompanyExists(false);
    setSelectedCompany(null);
    setCurrentStep(1); // → Document upload
  }, []);

  // ── Step 1: Document upload ──

  const uploadDocument = useCallback(async (uri: string, mimeType: string) => {
    setIsUploading(true);
    setError(null);
    try {
      // Step 1: ensure a BUNDLE_PAYMENT wizard session exists (idempotent within hook lifetime).
      let sessionId = wizardSessionId;
      if (!sessionId) {
        const session = await wizardApi.createSession({
          workflow_code: 'BUNDLE_PAYMENT',
          solicitud_type: 'expedicion',
        });
        sessionId = session.session_id;
        setWizardSessionId(sessionId);
      }

      // Step 2: derive a sensible filename so backend MIME detection picks the right extension.
      const ext = mimeType === 'application/pdf' ? 'pdf'
        : mimeType === 'image/png' ? 'png'
        : mimeType === 'image/webp' ? 'webp'
        : 'jpg';
      const fileName = `${BUNDLE_COMPANY_DOCUMENT_CODE}.${ext}`;

      // Step 3: upload via the canonical wizard preview endpoint.
      const result = await wizardApi.previewDocument(
        sessionId,
        BUNDLE_COMPANY_DOCUMENT_CODE,
        uri,
        fileName,
      );
      setDocumentPreview(result);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.response?.data?.message || 'Upload failed');
    } finally { setIsUploading(false); }
  }, [wizardSessionId]);

  const deleteDocument = useCallback(async () => {
    if (wizardSessionId) {
      try {
        await wizardApi.deleteDocument(wizardSessionId, BUNDLE_COMPANY_DOCUMENT_CODE);
      } catch {
        // ignore — frontend state is the source of truth for the wizard UI
      }
    }
    setDocumentPreview(null);
  }, [wizardSessionId]);

  // ── Step 2: Classification ──

  const loadClassification = useCallback(async () => {
    if (!documentPreview?.extraction) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await bundleApi.classifyPreview(documentPreview.extraction, selectedZoneId || undefined);
      setClassificationPreview(data);
      // Auto-populate if resolved
      if (data.zone_resolved && data.zone && !selectedZoneId) {
        setSelectedZoneId(data.zone.id);
      }
      if (data.classification?.commerce_type && !selectedCommerceType) {
        setSelectedCommerceType(data.classification.commerce_type);
      }
      // Auto-populate editable fields from extraction (like web)
      const ext = data.extracted_data || {};
      const empresa = ext.empresa || ext;
      const ubicacion = ext.ubicacion || ext;
      const actividad = ext.actividad || ext;
      setEditedFieldsState((prev) => ({
        legalName: prev.legalName || empresa.denominacion_social || empresa.legal_name || null,
        registrationNumber: prev.registrationNumber || empresa.numero_registro || empresa.registration_number || null,
        nif: prev.nif || empresa.nif || null,
        localidad: prev.localidad || ubicacion.localidad || null,
        provincia: prev.provincia || ubicacion.provincia || null,
        sector: prev.sector || actividad.sector || null,
        objetoSocial: prev.objetoSocial || actividad.objeto_social || null,
        formaJuridica: prev.formaJuridica || empresa.forma_juridica || null,
      }));
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Classification failed');
    } finally { setIsLoading(false); }
  }, [documentPreview, selectedZoneId, selectedCommerceType]);

  // Refetch classification when zone changes (like web)
  useEffect(() => {
    if (currentStep === 2 && documentPreview?.extraction && selectedZoneId) {
      setSelectedCommerceType(null); // Reset category on zone change
      loadClassification();
    }
  }, [selectedZoneId]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Step 3: Obligations ──

  const loadObligations = useCallback(async () => {
    setIsInitiating(true);
    setError(null);
    try {
      let data: BundleInitiateResponse;
      if (companyExists && selectedCompany) {
        data = await bundleApi.initiate(selectedCompany.id);
      } else if (documentPreview?.extraction) {
        // Inject ALL user-edited fields into extraction (like web lines 354-365)
        const extraction = { ...documentPreview.extraction };
        const ef = editedFields;
        const empresaObj = (extraction.empresa || extraction) as Record<string, unknown>;
        const ubicacionObj = (extraction.ubicacion || extraction) as Record<string, unknown>;
        const actividadObj = (extraction.actividad || extraction) as Record<string, unknown>;
        if (ef.legalName) empresaObj.denominacion_social = ef.legalName;
        if (ef.registrationNumber) empresaObj.numero_registro = ef.registrationNumber;
        if (ef.nif) empresaObj.nif = ef.nif;
        if (ef.formaJuridica) empresaObj.forma_juridica = ef.formaJuridica;
        if (ef.localidad) ubicacionObj.localidad = ef.localidad;
        if (ef.provincia) ubicacionObj.provincia = ef.provincia;
        if (ef.sector) actividadObj.sector = ef.sector;
        if (ef.objetoSocial) actividadObj.objeto_social = ef.objetoSocial;

        data = await bundleApi.initiateFromUpload(
          extraction, undefined, selectedZoneId || undefined, selectedCommerceType || undefined
        );
      } else {
        throw new Error('No company or document');
      }
      setLicenseData(data);
      if (data.company) setSelectedCompany(data.company);
      // Auto-select all payable (like web)
      const payableIds = new Set(
        (data.obligations || []).filter((o) => o.is_payable).map((o) => o.id)
      );
      setSelectedObligationIds(payableIds);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.response?.data?.message_es || 'Failed to load obligations');
    } finally { setIsInitiating(false); }
  }, [companyExists, selectedCompany, documentPreview, selectedZoneId, selectedCommerceType]);

  const toggleObligation = useCallback((id: string) => {
    setSelectedObligationIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const selectAllObligations = useCallback(() => {
    if (!licenseData) return;
    setSelectedObligationIds(new Set(
      licenseData.obligations.filter((o) => o.is_payable).map((o) => o.id)
    ));
  }, [licenseData]);

  const deselectAllObligations = useCallback(() => setSelectedObligationIds(new Set()), []);

  const setSelectedMode = useCallback((mode: ProcessingMode) => {
    setSelectedModeState(mode);
    if (mode === 'consolidated' && licenseData) {
      // Auto-select all payable in consolidated mode (like web)
      setSelectedObligationIds(new Set(
        licenseData.obligations.filter((o) => o.is_payable).map((o) => o.id)
      ));
    }
  }, [licenseData]);

  // ── Step 4: Payment ──

  const submitPayment = useCallback(async () => {
    if (paymentLockRef.current || !licenseData || !paymentMethod) return;
    paymentLockRef.current = true;
    setIsPaymentProcessing(true);
    setError(null);
    try {
      const result = await bundleApi.initiatePayment({
        license_id: licenseData.license_id,
        processing_mode: selectedMode,
        payment_method: paymentMethod,
        selected_obligation_ids: Array.from(selectedObligationIds),
        ...(paymentMethod === 'mobile_money' && phoneNumber ? { phone_number: phoneNumber } : {}),
      });
      if (result.redirect_url) {
        await Linking.openURL(result.redirect_url);
      }
      setPaymentResult(result);
      setCurrentStep(5); // → Confirmation
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.response?.data?.message_es || 'Payment failed');
    } finally {
      setIsPaymentProcessing(false);
      paymentLockRef.current = false;
    }
  }, [licenseData, paymentMethod, selectedMode, selectedObligationIds, phoneNumber]);

  // ── Navigation (aligned with web) ──

  const canGoNext = (() => {
    switch (currentStep) {
      case 0: return !!selectedCompany || !companyExists;
      case 1: return !!documentPreview;
      case 2: return !!editedFields.registrationNumber && !!editedFields.legalName && !!editedFields.localidad && !!selectedZoneId && !!selectedCommerceType;
      case 3: return !!licenseData && !licenseData.already_complete && selectedObligationIds.size > 0;
      case 4: return !!paymentMethod && (paymentMethod !== 'mobile_money' || phoneNumber.length >= 9);
      default: return false;
    }
  })();

  const canGoBack = currentStep > 0 && currentStep < 5;

  const goNext = useCallback(async () => {
    setError(null);
    if (currentStep === 0) {
      if (companyExists && selectedCompany) {
        // Existing company → skip upload+classification → obligations
        setIsLoading(true);
        try {
          const data = await bundleApi.initiate(selectedCompany.id);
          setLicenseData(data);
          if (data.company) setSelectedCompany(data.company);
          setSelectedObligationIds(new Set(
            (data.obligations || []).filter((o) => o.is_payable).map((o) => o.id)
          ));
          setCurrentStep(3); // → Obligations (skip 1+2)
        } catch (e: any) {
          setError(e?.response?.data?.detail || 'Failed to initiate');
        } finally { setIsLoading(false); }
        return;
      }
      setCurrentStep(1); // → Document upload
      return;
    }
    if (currentStep === 1) {
      // After upload → classification
      await loadClassification();
      setCurrentStep(2);
      return;
    }
    if (currentStep === 2) {
      // After classification → load obligations
      await loadObligations();
      setCurrentStep(3);
      return;
    }
    if (currentStep === 3) {
      setCurrentStep(4); // → Payment
      return;
    }
    if (currentStep === 4) {
      await submitPayment(); // Handles step advance internally
      return;
    }
  }, [currentStep, companyExists, selectedCompany, loadClassification, loadObligations, submitPayment]);

  // goBack aligned with web: obligations → company_id (existing) or classification (new)
  const goBack = useCallback(() => {
    if (currentStep === 3 && companyExists) {
      setCurrentStep(0); // Skip back over upload+classification
    } else if (currentStep === 3 && !companyExists) {
      setCurrentStep(2); // Back to classification (not upload)
    } else if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1);
    }
  }, [currentStep, companyExists]);

  const clearError = useCallback(() => setError(null), []);

  return {
    currentStep, totalSteps, canGoNext, canGoBack, goNext, goBack,
    myCompanies, searchResults, selectedCompany, companyExists,
    isLoadingCompanies, isSearching,
    loadMyCompanies, searchCompany, selectCompany, clearCompanySelection, requestNewCompany,
    documentPreview, isUploading, uploadDocument, deleteDocument,
    classificationPreview, selectedZoneId, selectedCommerceType, editedFields,
    setSelectedZoneId, setSelectedCommerceType, setEditedField, loadClassification,
    licenseData, selectedMode, selectedObligationIds, isInitiating,
    setSelectedMode, toggleObligation, selectAllObligations, deselectAllObligations, loadObligations,
    paymentMethod, phoneNumber, isPaymentProcessing,
    setPaymentMethod, setPhoneNumber, submitPayment,
    paymentResult,
    error, isLoading, clearError,
  };
}
