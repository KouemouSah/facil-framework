/**
 * Shared company form (create + edit).
 *
 * Uses React Hook Form + Zod. The full set of fields the backend accepts is
 * larger; we surface the required ones plus the most common optional fields.
 * Power-user fields (capital_social, etc.) can come in a "Advanced" section
 * post-MVP — not blocking V1.
 */

import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Button, HelperText, Text, TextInput } from 'react-native-paper';
import { Controller, useForm, type SubmitHandler } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import type { CompanyFormValues } from '../types/companies.types';

const buildSchema = (t: (k: string) => string) =>
  z.object({
    legal_name: z.string().min(2, t('companies.form.validation.legalNameRequired')),
    tax_id: z.string().min(2, t('companies.form.validation.taxIdRequired')),
    representante_legal: z
      .string()
      .min(2, t('companies.form.validation.representanteRequired')),
    regimen_fiscal: z
      .enum(['bundle', 'declarativo', 'exento', 'pendiente'])
      .nullable()
      .optional(),
    zone_id: z.string().nullable().optional(),
    commerce_type: z.string().nullable().optional(),
    forma_juridica: z.string().nullable().optional(),
    sector_actividad: z.string().nullable().optional(),
    address: z.string().nullable().optional(),
    email: z
      .string()
      .email(t('companies.form.validation.emailInvalid'))
      .or(z.literal(''))
      .nullable()
      .optional(),
    phone: z.string().nullable().optional(),
  });

interface CompanyFormProps {
  defaultValues?: Partial<CompanyFormValues>;
  submitting?: boolean;
  onSubmit: SubmitHandler<CompanyFormValues>;
  submitLabelKey?: string;
}

const EMPTY_DEFAULTS: CompanyFormValues = {
  legal_name: '',
  tax_id: '',
  representante_legal: '',
  regimen_fiscal: null,
  zone_id: null,
  commerce_type: null,
  forma_juridica: null,
  sector_actividad: null,
  address: null,
  email: null,
  phone: null,
};

export function CompanyForm({
  defaultValues,
  submitting,
  onSubmit,
  submitLabelKey = 'companies.form.actions.submit',
}: CompanyFormProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const schema = useMemo(() => buildSchema(t), [t]);

  const {
    control,
    handleSubmit,
    formState: { errors, isValid },
  } = useForm<CompanyFormValues>({
    resolver: zodResolver(schema),
    mode: 'onChange',
    defaultValues: { ...EMPTY_DEFAULTS, ...(defaultValues ?? {}) },
  });

  return (
    <View style={styles.container}>
      <FormField
        name="legal_name"
        control={control}
        labelKey="companies.form.fields.legalName"
        error={errors.legal_name?.message}
        autoCapitalize="words"
      />
      <FormField
        name="tax_id"
        control={control}
        labelKey="companies.form.fields.taxId"
        error={errors.tax_id?.message}
      />
      <FormField
        name="representante_legal"
        control={control}
        labelKey="companies.form.fields.representanteLegal"
        error={errors.representante_legal?.message}
        autoCapitalize="words"
      />
      <FormField
        name="forma_juridica"
        control={control}
        labelKey="companies.form.fields.formaJuridica"
        error={errors.forma_juridica?.message}
      />
      <FormField
        name="sector_actividad"
        control={control}
        labelKey="companies.form.fields.sectorActividad"
        error={errors.sector_actividad?.message}
      />
      <FormField
        name="address"
        control={control}
        labelKey="companies.form.fields.address"
        error={errors.address?.message}
      />
      <FormField
        name="email"
        control={control}
        labelKey="companies.form.fields.email"
        error={errors.email?.message}
        keyboardType="email-address"
        autoCapitalize="none"
      />
      <FormField
        name="phone"
        control={control}
        labelKey="companies.form.fields.phone"
        error={errors.phone?.message}
        keyboardType="phone-pad"
      />

      <Text variant="bodySmall" style={[styles.note, { color: colors.onSurfaceVariant }]}>
        {t('companies.form.classificationHint')}
      </Text>

      <Button
        mode="contained"
        onPress={handleSubmit(onSubmit)}
        disabled={submitting || !isValid}
        loading={submitting}
        style={styles.submit}
      >
        {t(submitLabelKey)}
      </Button>
    </View>
  );
}

interface FormFieldProps {
   
  control: any;
  name: keyof CompanyFormValues;
  labelKey: string;
  error?: string;
  autoCapitalize?: 'none' | 'sentences' | 'words' | 'characters';
  keyboardType?: 'default' | 'email-address' | 'phone-pad';
}

function FormField({
  control,
  name,
  labelKey,
  error,
  autoCapitalize = 'sentences',
  keyboardType = 'default',
}: FormFieldProps) {
  const { t } = useTranslation();
  return (
    <View>
      <Controller
        control={control}
        name={name}
        render={({ field: { value, onChange, onBlur } }) => (
          <TextInput
            label={t(labelKey)}
            value={(value ?? '') as string}
            onChangeText={(v) => onChange(v === '' ? null : v)}
            onBlur={onBlur}
            mode="outlined"
            autoCapitalize={autoCapitalize}
            keyboardType={keyboardType}
            error={!!error}
            style={styles.input}
          />
        )}
      />
      {error ? <HelperText type="error">{error}</HelperText> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: 12 },
  input: { backgroundColor: 'transparent' },
  note: { marginTop: 8 },
  submit: { marginTop: 16 },
});
