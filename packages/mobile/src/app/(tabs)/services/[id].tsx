/**
 * Service Detail Screen — Native Android v2
 *
 * Compact flat layout:
 * - Header: back + service name
 * - Info strip: ministry · category · code
 * - Price prominent + processing time
 * - Documents flat list
 * - Procedures collapsed by default
 * - Related services chips
 * - Disabled "Lancer demande" button with tooltip
 */

import { useCallback } from 'react';
import {
  StyleSheet,
  View,
  ScrollView,
  FlatList,
  Pressable,
  type ListRenderItemInfo,
} from 'react-native';
import { Text, Button, Divider, IconButton, ActivityIndicator } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import { formatCurrency } from '@core/utils/format';
import { useServiceDetail } from '@modules/fiscal-services';
import type { RelatedServiceItem, ProcedureDetailItem } from '@modules/fiscal-services';

export default function ServiceDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { t, i18n } = useTranslation();
  const { colors, spacing } = useAppTheme();
  const lang = (i18n.language || 'es') as string;

  const serviceId = Number(id);
  const { data: service, isLoading, isError } = useServiceDetail(serviceId, lang);

  const handleBack = useCallback(() => router.back(), [router]);
  const handleRelatedPress = useCallback((rid: number) => router.push(`/(tabs)/services/${rid}` as never), [router]);
  const handleStartRequest = useCallback(() => {
    if (!service?.service_code) return;
    // Navigate to wizard creation with workflow_code derived from service
    // The workflow_code mapping is handled by the backend
    router.push(`/wizard/create?workflow_code=${service.service_code}&service_id=${serviceId}` as never);
  }, [service, serviceId, router]);

  if (isLoading) {
    return (
      <SafeAreaView style={[styles.container, styles.centered, { backgroundColor: colors.background }]} edges={['top']}>
        <ActivityIndicator size="large" color={colors.primary} />
      </SafeAreaView>
    );
  }

  if (isError || !service) {
    return (
      <SafeAreaView style={[styles.container, styles.centered, { backgroundColor: colors.background }]} edges={['top']}>
        <MaterialCommunityIcons name="alert-circle-outline" size={48} color={colors.error} />
        <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant, marginTop: 12 }}>{t('common.error')}</Text>
        <Button mode="outlined" onPress={handleBack} style={{ marginTop: 12 }}>{t('common.back')}</Button>
      </SafeAreaView>
    );
  }

  const isFree = service.pricing.expedition_price === 0 && service.pricing.renewal_price === 0;
  const hasRenewal = service.pricing.renewal_price > 0 && service.pricing.renewal_price !== service.pricing.expedition_price;
  const allRelated = [...service.related_services, ...service.child_services];

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
      {/* Top bar */}
      <View style={[styles.topBar, { backgroundColor: colors.surface, borderBottomColor: colors.outlineVariant }]}>
        <IconButton icon="arrow-left" size={24} onPress={handleBack} />
        <Text variant="titleMedium" style={{ color: colors.onSurface, fontWeight: '600', flex: 1 }} numberOfLines={1}>
          {service.name}
        </Text>
      </View>

      <ScrollView contentContainerStyle={{ paddingBottom: 24 }} showsVerticalScrollIndicator={false}>

        {/* ═══ INFO STRIP (green accent) ═══ */}
        <View style={[styles.infoStrip, { paddingHorizontal: spacing.md, paddingVertical: 10 }]}>
          {service.ministry && (
            <View style={styles.infoItem}>
              <MaterialCommunityIcons name="domain" size={14} color="#2E7D32" />
              <Text variant="labelSmall" style={{ color: '#2E7D32', fontWeight: '600', marginLeft: 4 }} numberOfLines={1}>
                {service.ministry.name}
              </Text>
            </View>
          )}
          {service.category && (
            <View style={styles.infoItem}>
              <MaterialCommunityIcons name="tag" size={14} color="#2E7D32" />
              <Text variant="labelSmall" style={{ color: '#2E7D32', marginLeft: 4 }}>
                {service.category.name}
              </Text>
            </View>
          )}
        </View>

        {/* ═══ PRICE ═══ */}
        <View style={{ paddingHorizontal: spacing.md, paddingVertical: 10 }}>
          {isFree ? (
            <View style={{ flexDirection: 'row', alignItems: 'center' }}>
              <MaterialCommunityIcons name="gift-outline" size={18} color={colors.primary} />
              <Text style={{ color: colors.primary, fontWeight: '700', fontSize: 16, marginLeft: 6 }}>
                {t('services.freeService')}
              </Text>
            </View>
          ) : (
            <View style={{ flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
              <Text variant="labelMedium" style={{ color: '#2E7D32' }}>{t('services.expedition')}:</Text>
              <Text style={{ color: colors.primary, fontWeight: '700', fontSize: 15 }}>
                {formatCurrency(service.pricing.expedition_price)}
              </Text>
              {hasRenewal && (
                <>
                  <Text style={{ color: colors.outline }}>|</Text>
                  <Text variant="labelMedium" style={{ color: '#2E7D32' }}>{t('services.renewal')}:</Text>
                  <Text style={{ color: '#2E7D32', fontWeight: '600', fontSize: 14 }}>
                    {formatCurrency(service.pricing.renewal_price)}
                  </Text>
                </>
              )}
              {service.processing_time_days != null && service.processing_time_days > 0 && (
                <>
                  <Text style={{ color: colors.outline }}>|</Text>
                  <View style={styles.metaChip}>
                    <MaterialCommunityIcons name="clock-outline" size={12} color={colors.primary} />
                    <Text style={{ color: colors.primary, fontSize: 11, fontWeight: '600', marginLeft: 3 }}>
                      {t('services.processingDays', { count: service.processing_time_days })}
                    </Text>
                  </View>
                </>
              )}
            </View>
          )}
        </View>

        <Divider />

        {/* ═══ DESCRIPTION ═══ */}
        {service.description && (
          <>
            <View style={{ paddingHorizontal: spacing.md, paddingVertical: 10 }}>
              <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant, lineHeight: 20 }}>
                {service.description}
              </Text>
            </View>
            <Divider />
          </>
        )}

        {/* ═══ DOCUMENTS (flat) ═══ */}
        {service.has_documents && service.documents.length > 0 && (
          <>
            <View style={{ paddingHorizontal: spacing.md, paddingTop: 12, paddingBottom: 4 }}>
              <Text variant="titleSmall" style={{ color: colors.onSurface, fontWeight: '600', marginBottom: 6 }}>
                {t('requests.documents')}
              </Text>
              {service.documents.map((doc, i) => (
                <View key={doc.id}>
                  {i > 0 && <Divider />}
                  <View style={styles.docRow}>
                    <MaterialCommunityIcons name="file-document-outline" size={18} color={colors.primary} />
                    <Text variant="bodySmall" style={{ color: colors.onSurface, flex: 1, marginLeft: 10 }} numberOfLines={2}>
                      {doc.name}
                    </Text>
                  </View>
                </View>
              ))}
            </View>
            <Divider />
          </>
        )}

        {/* ═══ PROCEDURES (collapsed) ═══ */}
        {service.has_procedures && service.procedures.length > 0 && (
          <>
            <View style={{ paddingHorizontal: spacing.md, paddingTop: 12, paddingBottom: 8 }}>
              <Text variant="titleSmall" style={{ color: colors.onSurface, fontWeight: '600', marginBottom: 6 }}>
                {t('services.procedures')}
              </Text>
              {service.procedures.map((proc: ProcedureDetailItem) => (
                <View key={proc.id} style={{ marginBottom: 8 }}>
                  <Text variant="bodySmall" style={{ color: colors.onSurface, fontWeight: '600' }}>
                    {proc.name}
                    {proc.total_estimated_minutes > 0 ? ` · ${proc.total_estimated_minutes} min` : ''}
                  </Text>
                  {proc.steps.map((step) => (
                    <View key={step.id} style={styles.stepRow}>
                      <View style={[styles.stepBadge, { backgroundColor: colors.primaryContainer }]}>
                        <Text style={{ color: colors.primary, fontSize: 10, fontWeight: '700' }}>{step.step_number}</Text>
                      </View>
                      <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, flex: 1 }} numberOfLines={2}>
                        {step.title || step.description || `Paso ${step.step_number}`}
                      </Text>
                    </View>
                  ))}
                </View>
              ))}
            </View>
            <Divider />
          </>
        )}

        {/* ═══ RELATED SERVICES ═══ */}
        {allRelated.length > 0 && (
          <View style={{ paddingTop: 12, paddingBottom: 8 }}>
            <Text variant="titleSmall" style={{ color: colors.onSurface, fontWeight: '600', marginBottom: 6, paddingHorizontal: spacing.md }}>
              {t('services.relatedServices')}
            </Text>
            <FlatList
              data={allRelated}
              keyExtractor={(item) => String(item.id)}
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={{ paddingHorizontal: spacing.md, gap: 8 }}
              renderItem={({ item }: ListRenderItemInfo<RelatedServiceItem>) => (
                <Pressable
                  style={[styles.relatedChip, { borderColor: colors.outlineVariant, backgroundColor: colors.surface }]}
                  onPress={() => handleRelatedPress(item.id)}
                >
                  <Text variant="bodySmall" style={{ color: colors.onSurface, fontWeight: '500' }} numberOfLines={1}>
                    {item.name}
                  </Text>
                  <Text style={{ color: colors.primary, fontSize: 11, fontWeight: '700', marginTop: 2 }}>
                    {(item.expedition_price ?? 0) === 0 ? t('services.freeService') : formatCurrency(item.expedition_price ?? 0)}
                  </Text>
                </Pressable>
              )}
            />
          </View>
        )}

        {/* ═══ LEGAL REFERENCE ═══ */}
        {service.legal_reference && (
          <>
            <Divider />
            <View style={{ paddingHorizontal: spacing.md, paddingVertical: 10 }}>
              <View style={styles.metaRow}>
                <MaterialCommunityIcons name="scale-balance" size={14} color={colors.outline} />
                <Text variant="labelSmall" style={{ color: colors.outline, marginLeft: 4, fontStyle: 'italic', flex: 1 }}>
                  {service.legal_reference}
                </Text>
              </View>
            </View>
          </>
        )}
        {/* ═══ CTA BUTTON (disabled, inside scroll) ═══ */}
        <View style={{ paddingHorizontal: spacing.md, paddingVertical: 16 }}>
          <Button
            mode="contained"
            onPress={handleStartRequest}
            icon="arrow-right"
            style={{ borderRadius: 8, opacity: 0.5 }}
            contentStyle={{ paddingVertical: 4 }}
            disabled
          >
            {t('services.startRequest')}
          </Button>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  centered: { justifyContent: 'center', alignItems: 'center' },
  topBar: { flexDirection: 'row', alignItems: 'center', borderBottomWidth: 1 },
  infoStrip: { gap: 4, backgroundColor: '#E8F5E9' },
  infoItem: { flexDirection: 'row', alignItems: 'center' },
  priceCard: { backgroundColor: '#FFFFFF', borderRadius: 12, padding: 14, borderLeftWidth: 4, borderLeftColor: '#0D6E3F' },
  priceRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', paddingVertical: 2 },
  metaChip: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#C8E6C9', borderRadius: 12, paddingHorizontal: 8, paddingVertical: 3 },
  metaRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap' },
  docRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8 },
  stepRow: { flexDirection: 'row', alignItems: 'center', marginTop: 4, gap: 8, paddingLeft: 4 },
  stepBadge: { width: 20, height: 20, borderRadius: 10, justifyContent: 'center', alignItems: 'center' },
  relatedChip: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, borderWidth: 1, minWidth: 120, maxWidth: 160 },
});
