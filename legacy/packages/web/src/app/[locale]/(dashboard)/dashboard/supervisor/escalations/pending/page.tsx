'use client';

/**
 * Pending Escalations Page - Supervisor View
 * List and manage pending escalations from agents
 *
 * @route /[locale]/dashboard/supervisor/escalations/pending
 * @date 2026-01-19
 */

import React, { useState, useRef, useCallback } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Loader2,
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  Search,
  RefreshCw,
  CheckCircle,
  UserCheck,
  Clock,
  Eye,
  ThumbsUp,
  XCircle,
} from 'lucide-react';
import apiClient from '@/core/api/client';
import { getApiErrorMessage } from '@/core/api/errors';
import Link from 'next/link';
import { toast } from 'sonner';
import { formatDistanceToNow } from 'date-fns';
import { es, fr, enUS } from 'date-fns/locale';
import type { Escalation, AgentListItem } from '../../types';
import { getPriorityLevel, PRIORITY_COLORS } from '../../types';

export default function PendingEscalationsPage() {
  const locale = useLocale();
  const queryClient = useQueryClient();
  const t = useTranslations('supervisor');
  const tCommon = useTranslations('common');

  const dateLocale = locale === 'es' ? es : locale === 'fr' ? fr : enUS;

  const [searchTerm, setSearchTerm] = useState('');
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [selectedEscalation, setSelectedEscalation] = useState<Escalation | null>(null);
  const [isDetailsDialogOpen, setIsDetailsDialogOpen] = useState(false);
  const [isResolveDialogOpen, setIsResolveDialogOpen] = useState(false);
  const [isReassignDialogOpen, setIsReassignDialogOpen] = useState(false);
  const [isApproveDialogOpen, setIsApproveDialogOpen] = useState(false);
  const [isRejectDialogOpen, setIsRejectDialogOpen] = useState(false);
  const [resolutionNotes, setResolutionNotes] = useState('');
  const [approveNotes, setApproveNotes] = useState('');
  const [rejectionReason, setRejectionReason] = useState('');
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isBulkDialogOpen, setIsBulkDialogOpen] = useState(false);
  const [bulkAction, setBulkAction] = useState<'resolve' | 'approve' | 'reject' | 'assign' | null>(null);
  const [bulkNotes, setBulkNotes] = useState('');

  // Focus management: ref to a stable element for focus restoration after dialogs close
  const refreshBtnRef = useRef<HTMLButtonElement>(null);
  const restoreFocus = useCallback(() => {
    // After dialog close, return focus to the refresh button (always present)
    requestAnimationFrame(() => refreshBtnRef.current?.focus());
  }, []);

  // Fetch pending escalations - uses GET /supervisor/escalations?status_filter=pending
  const { data: escalations, isLoading, isError, error, refetch } = useQuery<Escalation[]>({
    queryKey: ['supervisor', 'escalations', 'pending'],
    queryFn: async () => {
      const response = await apiClient.get('/supervisor/escalations', {
        params: { status_filter: 'pending' }
      });
      return response.data;
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Fetch available agents for reassignment - uses GET /supervisor/agents
  const { data: agents } = useQuery<AgentListItem[]>({
    queryKey: ['supervisor', 'agents', 'available'],
    queryFn: async () => {
      const response = await apiClient.get('/supervisor/agents', {
        params: { include_unavailable: false }
      });
      return response.data;
    },
    enabled: isReassignDialogOpen,
  });

  // Resolve escalation mutation - uses POST /supervisor/escalations/{queue_id}/resolve
  const resolveMutation = useMutation({
    mutationFn: async ({ queueId, notes }: { queueId: string; notes: string }) => {
      const response = await apiClient.post(`/supervisor/escalations/${queueId}/resolve`, {
        resolution_notes: notes,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['supervisor', 'escalations'] });
      setIsResolveDialogOpen(false);
      setSelectedEscalation(null);
      setResolutionNotes('');
      toast.success(t('escalations.resolved') || 'Escalation resolved');
      restoreFocus();
    },
    onError: (err: unknown) => {
      toast.error(getApiErrorMessage(err, tCommon('error'), tCommon));
    },
  });

  // Assign escalation mutation - uses POST /supervisor/escalations/{queue_id}/assign
  const assignMutation = useMutation({
    mutationFn: async ({ queueId, agentId }: { queueId: string; agentId: string }) => {
      const response = await apiClient.post(`/supervisor/escalations/${queueId}/assign`, null, {
        params: { agent_id: agentId }
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['supervisor', 'escalations'] });
      setIsReassignDialogOpen(false);
      setSelectedEscalation(null);
      setSelectedAgentId('');
      toast.success(t('escalations.reassign') || 'Escalation assigned');
      restoreFocus();
    },
    onError: (err: unknown) => {
      toast.error(getApiErrorMessage(err, tCommon('error'), tCommon));
    },
  });

  // Approve escalation directly — POST /supervisor/escalations/{queue_id}/approve
  const approveMutation = useMutation({
    mutationFn: async ({ queueId, notes }: { queueId: string; notes: string }) => {
      const response = await apiClient.post(`/supervisor/escalations/${queueId}/approve`, {
        notes: notes || null,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['supervisor', 'escalations'] });
      queryClient.invalidateQueries({ queryKey: ['supervisor', 'dashboard'] });
      setIsApproveDialogOpen(false);
      setSelectedEscalation(null);
      setApproveNotes('');
      toast.success(t('escalations.approved'));
      restoreFocus();
    },
    onError: (err: unknown) => {
      toast.error(getApiErrorMessage(err, tCommon('error'), tCommon));
    },
  });

  // Reject escalation directly — POST /supervisor/escalations/{queue_id}/reject
  const rejectMutation = useMutation({
    mutationFn: async ({ queueId, reason }: { queueId: string; reason: string }) => {
      const response = await apiClient.post(`/supervisor/escalations/${queueId}/reject`, {
        rejection_reason: reason,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['supervisor', 'escalations'] });
      queryClient.invalidateQueries({ queryKey: ['supervisor', 'dashboard'] });
      setIsRejectDialogOpen(false);
      setSelectedEscalation(null);
      setRejectionReason('');
      toast.success(t('escalations.rejected'));
      restoreFocus();
    },
    onError: (err: unknown) => {
      toast.error(getApiErrorMessage(err, tCommon('error'), tCommon));
    },
  });

  // Bulk action mutation
  const bulkMutation = useMutation({
    mutationFn: async ({ action, ids, notes }: { action: string; ids: string[]; notes: string }) => {
      const body: Record<string, unknown> = {
        request_ids: ids,
        action,
      };
      if (action === 'resolve') body.resolution_notes = notes;
      if (action === 'approve') body.notes = notes || undefined;
      if (action === 'reject') body.rejection_reason = notes;
      const response = await apiClient.post('/supervisor/escalations/bulk-action', body);
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['supervisor', 'escalations'] });
      queryClient.invalidateQueries({ queryKey: ['supervisor', 'dashboard'] });
      setIsBulkDialogOpen(false);
      setSelectedIds(new Set());
      setBulkAction(null);
      setBulkNotes('');
      if (data.failed?.length > 0) {
        toast.warning(t('escalations.bulkPartial', { processed: data.processed, failed: data.failed.length }));
      } else {
        toast.success(t('escalations.bulkSuccess', { count: data.processed }));
      }
      restoreFocus();
    },
    onError: (err: unknown) => {
      toast.error(getApiErrorMessage(err, tCommon('error'), tCommon));
    },
  });

  // Filter escalations
  const filteredEscalations = escalations?.filter((esc) => {
    const matchesSearch =
      (esc.case_reference || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (esc.escalated_by_name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (esc.reason || '').toLowerCase().includes(searchTerm.toLowerCase());
    const priorityLevel = getPriorityLevel(esc.priority_score);
    const matchesPriority = priorityFilter === 'all' || priorityLevel === priorityFilter;
    return matchesSearch && matchesPriority;
  });

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (!filteredEscalations) return;
    if (selectedIds.size === filteredEscalations.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredEscalations.map(e => e.queue_id)));
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center space-y-4">
          <Loader2 className="h-10 w-10 animate-spin text-primary mx-auto" />
          <p className="text-muted-foreground">{tCommon('loading')}</p>
        </div>
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="space-y-6">
        <Card className="border-destructive/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              {tCommon('error')}
            </CardTitle>
            <CardDescription>
              {(error as Error)?.message || tCommon('errorGeneric')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" onClick={() => refetch()}>
              {tCommon('retry')}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/${locale}/dashboard/supervisor`}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <AlertTriangle className="h-6 w-6 text-orange-500" />
            {t('nav.pendingEscalations')}
            {(filteredEscalations?.length || 0) > 0 && (
              <Badge variant="destructive" className="ml-2">
                {filteredEscalations?.length}
              </Badge>
            )}
          </h1>
          <p className="text-muted-foreground">{t('escalations.title')}</p>
        </div>
      </div>

      {/* Search and filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={tCommon('search')}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={priorityFilter} onValueChange={setPriorityFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder={t('escalations.priority')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{tCommon('all')}</SelectItem>
                <SelectItem value="critical">{t('escalations.critical')}</SelectItem>
                <SelectItem value="high">{t('escalations.high')}</SelectItem>
                <SelectItem value="medium">{t('escalations.medium')}</SelectItem>
                <SelectItem value="low">{t('escalations.low')}</SelectItem>
              </SelectContent>
            </Select>
            <Button ref={refreshBtnRef} variant="outline" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4 mr-2" />
              {tCommon('refresh')}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Bulk Action Bar */}
      {selectedIds.size > 0 && (
        <Card className="border-primary/50 bg-primary/5">
          <CardContent className="py-3 flex items-center justify-between">
            <span className="text-sm font-medium">
              {t('escalations.selected', { count: selectedIds.size })}
            </span>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => { setBulkAction('resolve'); setBulkNotes(''); setIsBulkDialogOpen(true); }}
              >
                <CheckCircle className="h-4 w-4 mr-1" />
                {t('escalations.bulkResolve')}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="text-green-600 hover:text-green-700 hover:bg-green-50"
                onClick={() => { setBulkAction('approve'); setBulkNotes(''); setIsBulkDialogOpen(true); }}
              >
                <ThumbsUp className="h-4 w-4 mr-1" />
                {t('escalations.bulkApprove')}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="text-red-600 hover:text-red-700 hover:bg-red-50"
                onClick={() => { setBulkAction('reject'); setBulkNotes(''); setIsBulkDialogOpen(true); }}
              >
                <XCircle className="h-4 w-4 mr-1" />
                {t('escalations.bulkReject')}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setSelectedIds(new Set())}
              >
                {tCommon('cancel')}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Escalations Table */}
      <Card>
        <CardContent className="pt-6">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    checked={filteredEscalations && filteredEscalations.length > 0 && selectedIds.size === filteredEscalations.length}
                    onCheckedChange={toggleSelectAll}
                    aria-label={t('escalations.selectAll')}
                  />
                </TableHead>
                <TableHead>{t('escalations.priority')}</TableHead>
                <TableHead>{t('escalations.reference')}</TableHead>
                <TableHead>{t('escalations.escalatedBy')}</TableHead>
                <TableHead>{t('escalations.reason')}</TableHead>
                <TableHead>{t('escalations.escalatedAt')}</TableHead>
                <TableHead className="text-right">{tCommon('actions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredEscalations?.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                    <CheckCircle className="h-8 w-8 mx-auto mb-2 text-green-500" />
                    {t('escalations.noPending')}
                  </TableCell>
                </TableRow>
              ) : (
                filteredEscalations?.map((esc) => {
                  const priorityLevel = getPriorityLevel(esc.priority_score);
                  return (
                    <TableRow key={esc.queue_id} className="cursor-pointer hover:bg-muted/50">
                      <TableCell>
                        <Checkbox
                          checked={selectedIds.has(esc.queue_id)}
                          onCheckedChange={() => toggleSelect(esc.queue_id)}
                          aria-label={`Select ${esc.case_reference || esc.queue_id}`}
                        />
                      </TableCell>
                      <TableCell>
                        <Badge className={PRIORITY_COLORS[priorityLevel]}>
                          {t(`escalations.${priorityLevel}`)}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div>
                          <p className="font-medium">{esc.case_reference || 'N/A'}</p>
                          <p className="text-xs text-muted-foreground">{t('workflowNames.' + esc.case_type)}</p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div>
                          <p>{esc.escalated_by_name}</p>
                          <p className="text-xs text-muted-foreground">{esc.escalated_by_email}</p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <p className="truncate max-w-[200px]">{esc.reason}</p>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1 text-sm text-muted-foreground">
                          <Clock className="h-3 w-3" />
                          {formatDistanceToNow(new Date(esc.escalated_at), {
                            addSuffix: true,
                            locale: dateLocale,
                          })}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1 flex-wrap">
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`${tCommon('view')} ${esc.case_reference || ''}`}
                            onClick={() => {
                              setSelectedEscalation(esc);
                              setIsDetailsDialogOpen(true);
                            }}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-green-600 hover:text-green-700 hover:bg-green-50"
                            aria-label={`${t('escalations.approve')} ${esc.case_reference || ''}`}
                            onClick={() => {
                              setSelectedEscalation(esc);
                              setIsApproveDialogOpen(true);
                            }}
                          >
                            <ThumbsUp className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-red-600 hover:text-red-700 hover:bg-red-50"
                            aria-label={`${t('escalations.reject')} ${esc.case_reference || ''}`}
                            onClick={() => {
                              setSelectedEscalation(esc);
                              setIsRejectDialogOpen(true);
                            }}
                          >
                            <XCircle className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            aria-label={`${t('escalations.resolve')} ${esc.case_reference || ''}`}
                            onClick={() => {
                              setSelectedEscalation(esc);
                              setIsResolveDialogOpen(true);
                            }}
                          >
                            <CheckCircle className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            aria-label={`${t('escalations.reassign')} ${esc.case_reference || ''}`}
                            onClick={() => {
                              setSelectedEscalation(esc);
                              setIsReassignDialogOpen(true);
                            }}
                          >
                            <UserCheck className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* View Details Dialog */}
      <Dialog open={isDetailsDialogOpen} onOpenChange={(open) => {
        setIsDetailsDialogOpen(open);
        if (!open) {
          setSelectedEscalation(null);
          restoreFocus();
        }
      }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{t('escalations.details')}</DialogTitle>
            <DialogDescription>
              {selectedEscalation?.case_reference || ''}
            </DialogDescription>
          </DialogHeader>
          {selectedEscalation && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-muted-foreground">{t('escalations.reference')}</Label>
                  <p className="font-medium">{selectedEscalation.case_reference || 'N/A'}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">{t('escalations.priority')}</Label>
                  <Badge className={PRIORITY_COLORS[getPriorityLevel(selectedEscalation.priority_score)]}>
                    {t(`escalations.${getPriorityLevel(selectedEscalation.priority_score)}`)}
                  </Badge>
                </div>
                <div>
                  <Label className="text-muted-foreground">{t('escalations.escalatedBy')}</Label>
                  <p>{selectedEscalation.escalated_by_name}</p>
                  <p className="text-xs text-muted-foreground">{selectedEscalation.escalated_by_email}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">{t('escalations.escalatedAt')}</Label>
                  <p>{new Date(selectedEscalation.escalated_at).toLocaleString(locale)}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">{t('escalations.caseType')}</Label>
                  <p>{t('workflowNames.' + selectedEscalation.case_type)}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">{tCommon('status')}</Label>
                  <Badge variant="outline">{t('escalationStatus.' + selectedEscalation.escalation_status)}</Badge>
                </div>
              </div>
              <div>
                <Label className="text-muted-foreground">{t('escalations.reason')}</Label>
                <p className="mt-1 p-3 bg-muted rounded-md">{selectedEscalation.reason}</p>
              </div>
              {selectedEscalation.assigned_to_name && (
                <div>
                  <Label className="text-muted-foreground">{t('escalations.assignedTo')}</Label>
                  <p className="mt-1">{selectedEscalation.assigned_to_name}</p>
                </div>
              )}
            </div>
          )}
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={() => setIsDetailsDialogOpen(false)}>
              {tCommon('close')}
            </Button>
            <Button
              variant="default"
              className="bg-green-600 hover:bg-green-700"
              onClick={() => {
                setIsDetailsDialogOpen(false);
                setIsApproveDialogOpen(true);
              }}
            >
              <ThumbsUp className="h-4 w-4 mr-2" />
              {t('escalations.approve')}
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                setIsDetailsDialogOpen(false);
                setIsRejectDialogOpen(true);
              }}
            >
              <XCircle className="h-4 w-4 mr-2" />
              {t('escalations.reject')}
            </Button>
            <Button
              onClick={() => {
                setIsDetailsDialogOpen(false);
                setIsResolveDialogOpen(true);
              }}
            >
              {t('escalations.resolve')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Resolve Dialog */}
      <Dialog open={isResolveDialogOpen} onOpenChange={(open) => {
        setIsResolveDialogOpen(open);
        if (!open) {
          setResolutionNotes('');
          restoreFocus();
        }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('escalations.resolve')}</DialogTitle>
            <DialogDescription>
              {t('escalations.resolveDescription', { reference: selectedEscalation?.case_reference || selectedEscalation?.id || '' })}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>{t('escalations.resolutionNotes')} *</Label>
              <Textarea
                value={resolutionNotes}
                onChange={(e) => setResolutionNotes(e.target.value)}
                placeholder={t('escalations.resolutionNotesPlaceholder')}
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsResolveDialogOpen(false)}>
              {tCommon('cancel')}
            </Button>
            <Button
              onClick={() => selectedEscalation && resolveMutation.mutate({ queueId: selectedEscalation.queue_id, notes: resolutionNotes })}
              disabled={resolveMutation.isPending || resolutionNotes.trim().length < 5}
            >
              {resolveMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {t('escalations.resolve')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Approve Dialog */}
      <Dialog open={isApproveDialogOpen} onOpenChange={(open) => {
        setIsApproveDialogOpen(open);
        if (!open) {
          setApproveNotes('');
          restoreFocus();
        }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ThumbsUp className="h-5 w-5 text-green-600" />
              {t('escalations.approveTitle')}
            </DialogTitle>
            <DialogDescription>
              {t('escalations.approveDescription', { reference: selectedEscalation?.case_reference || '' })}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-3 bg-muted rounded-md">
              <p className="text-sm font-medium">{t('escalations.reason')}</p>
              <p className="text-sm text-muted-foreground mt-1">{selectedEscalation?.reason}</p>
            </div>
            <div>
              <Label>{t('escalations.approveNotes')}</Label>
              <Textarea
                value={approveNotes}
                onChange={(e) => setApproveNotes(e.target.value)}
                placeholder={t('escalations.approveNotesPlaceholder')}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsApproveDialogOpen(false)}>
              {tCommon('cancel')}
            </Button>
            <Button
              className="bg-green-600 hover:bg-green-700"
              onClick={() => selectedEscalation && approveMutation.mutate({
                queueId: selectedEscalation.queue_id,
                notes: approveNotes,
              })}
              disabled={approveMutation.isPending}
            >
              {approveMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {t('escalations.confirmApprove')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reject Dialog */}
      <Dialog open={isRejectDialogOpen} onOpenChange={(open) => {
        setIsRejectDialogOpen(open);
        if (!open) {
          setRejectionReason('');
          restoreFocus();
        }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <XCircle className="h-5 w-5 text-red-600" />
              {t('escalations.rejectTitle')}
            </DialogTitle>
            <DialogDescription>
              {t('escalations.rejectDescription', { reference: selectedEscalation?.case_reference || '' })}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-3 bg-muted rounded-md">
              <p className="text-sm font-medium">{t('escalations.reason')}</p>
              <p className="text-sm text-muted-foreground mt-1">{selectedEscalation?.reason}</p>
            </div>
            <div>
              <Label>{t('escalations.rejectionReason')} *</Label>
              <Textarea
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                placeholder={t('escalations.rejectionReasonPlaceholder')}
                rows={4}
              />
              <p className="text-xs text-muted-foreground mt-1">
                {rejectionReason.length}/500 ({t('escalations.rejectionMinChars')})
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsRejectDialogOpen(false)}>
              {tCommon('cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={() => selectedEscalation && rejectMutation.mutate({
                queueId: selectedEscalation.queue_id,
                reason: rejectionReason,
              })}
              disabled={rejectMutation.isPending || rejectionReason.trim().length < 5}
            >
              {rejectMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {t('escalations.confirmReject')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Assign Dialog */}
      <Dialog open={isReassignDialogOpen} onOpenChange={(open) => {
        setIsReassignDialogOpen(open);
        if (!open) {
          setSelectedAgentId('');
          restoreFocus();
        }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('escalations.reassign')}</DialogTitle>
            <DialogDescription>
              {t('escalations.reassignDescription', { reference: selectedEscalation?.case_reference || selectedEscalation?.id || '' })}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>{t('escalations.selectAgent')}</Label>
              <Select value={selectedAgentId} onValueChange={setSelectedAgentId}>
                <SelectTrigger>
                  <SelectValue placeholder={t('escalations.selectAgentPlaceholder')} />
                </SelectTrigger>
                <SelectContent>
                  {agents?.map((agent) => (
                    <SelectItem key={agent.agent_profile_id} value={agent.agent_profile_id}>
                      {agent.agent_name} ({agent.capacity_percentage.toFixed(0)}%) - {t('workloadStatus.' + agent.workload_status)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsReassignDialogOpen(false)}>
              {tCommon('cancel')}
            </Button>
            <Button
              onClick={() => selectedEscalation && assignMutation.mutate({ queueId: selectedEscalation.queue_id, agentId: selectedAgentId })}
              disabled={assignMutation.isPending || !selectedAgentId}
            >
              {assignMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {t('escalations.reassign')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bulk Action Confirm Dialog */}
      <Dialog open={isBulkDialogOpen} onOpenChange={(open) => {
        setIsBulkDialogOpen(open);
        if (!open) {
          setBulkNotes('');
          restoreFocus();
        }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('escalations.bulkConfirm')}</DialogTitle>
            <DialogDescription>
              {t('escalations.bulkConfirmDescription', { count: selectedIds.size })}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {(bulkAction === 'resolve' || bulkAction === 'reject') && (
              <div>
                <Label>
                  {bulkAction === 'resolve' ? t('escalations.resolutionNotes') : t('escalations.rejectionReason')} *
                </Label>
                <Textarea
                  value={bulkNotes}
                  onChange={(e) => setBulkNotes(e.target.value)}
                  placeholder={bulkAction === 'resolve' ? t('escalations.resolutionNotesPlaceholder') : t('escalations.rejectionReasonPlaceholder')}
                  rows={4}
                />
              </div>
            )}
            {bulkAction === 'approve' && (
              <div>
                <Label>{t('escalations.approveNotes')}</Label>
                <Textarea
                  value={bulkNotes}
                  onChange={(e) => setBulkNotes(e.target.value)}
                  placeholder={t('escalations.approveNotesPlaceholder')}
                  rows={3}
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsBulkDialogOpen(false)}>
              {tCommon('cancel')}
            </Button>
            <Button
              onClick={() => bulkAction && bulkMutation.mutate({
                action: bulkAction,
                ids: Array.from(selectedIds),
                notes: bulkNotes,
              })}
              disabled={
                bulkMutation.isPending ||
                ((bulkAction === 'resolve' || bulkAction === 'reject') && bulkNotes.trim().length < 5)
              }
              variant={bulkAction === 'reject' ? 'destructive' : bulkAction === 'approve' ? 'default' : 'default'}
              className={bulkAction === 'approve' ? 'bg-green-600 hover:bg-green-700' : ''}
            >
              {bulkMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {bulkAction && t(`escalations.bulk${bulkAction.charAt(0).toUpperCase() + bulkAction.slice(1)}`)}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
