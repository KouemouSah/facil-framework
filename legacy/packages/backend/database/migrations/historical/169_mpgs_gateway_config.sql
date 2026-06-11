-- Migration 169: MPGS (Mastercard Payment Gateway Services) configuration
-- Depends on: 167_payment_architecture_coherence.sql (adds gateway_type, supported_payment_methods, is_primary)
--
-- MPGS is a sub-processor of ECOBANK for card payments.
-- It does NOT need its own row in bank_configurations.
-- Routing is handled by PaymentProcessorRegistry (ECOBANK_MPGS key)
-- and env vars (MPGS_MERCHANT_ID, MPGS_API_PASSWORD).
--
-- This migration updates the ECOBANK gateway_type comment to document MPGS.

-- Update gateway_type comment to document MPGS sub-processor
COMMENT ON COLUMN bank_configurations.gateway_type IS
    'Gateway type: bange, ecobank (includes MPGS for cards via Mastercard), null (not integrated)';

-- Add index for gateway health check queries
CREATE INDEX IF NOT EXISTS idx_bank_config_gateway_type
    ON bank_configurations(gateway_type)
    WHERE gateway_type IS NOT NULL AND is_active = true;
