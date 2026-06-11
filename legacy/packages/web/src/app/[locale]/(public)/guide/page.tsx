'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  FileText,
  HelpCircle,
  BookOpen,
  Download,
  CheckCircle2,
  ExternalLink,
  ClipboardList,
  Calculator,
  Send,
  FileCheck,
  Scale,
  Gavel,
  Building2,
  Users,
  Eye,
  AlertTriangle,
} from 'lucide-react';
import Breadcrumb from '@/components/ui/breadcrumb';

type TabType = 'workflow' | 'legislation' | 'downloads' | 'faq';

// Declaration workflow steps
const WORKFLOW_STEPS = [
  { icon: ClipboardList, key: 'step1' },
  { icon: Calculator, key: 'step2' },
  { icon: FileText, key: 'step3' },
  { icon: Send, key: 'step4' },
  { icon: FileCheck, key: 'step5' },
];

// Legislation categories with links
const LEGISLATION_ITEMS = [
  {
    icon: Scale,
    key: 'taxCode',
    links: [
      { key: 'Link1', url: '/documents/legislacion/CODIGOS-DE-INGRESOS-2025.pdf' },
      { key: 'Link2', url: '#' }, // Placeholder for General Tax Law
    ]
  },
  {
    icon: Gavel,
    key: 'decrees',
    links: [
      { key: 'Link1', url: '#' },
      { key: 'Link2', url: '#' },
    ]
  },
  {
    icon: Building2,
    key: 'procedures',
    links: [
      { key: 'Link1', url: '#' },
      { key: 'Link2', url: '#' },
    ]
  },
  {
    icon: Users,
    key: 'obligations',
    links: [
      { key: 'Link1', url: '#' },
      { key: 'Link2', url: '#' },
    ]
  },
];

// Real Downloadable PDF forms
const DOWNLOAD_ITEMS = [
  {
    key: 'retenciones3pctResidentes',
    filename: '3_RESIDENTES_PETROLERO.pdf',
    category: 'withholding',
    format: 'PDF',
    size: '~250KB'
  },
  {
    key: 'retenciones5pctResidentes',
    filename: '5_RESIDENTES_PETROLERO.pdf',
    category: 'withholding',
    format: 'PDF',
    size: '~240KB'
  },
  {
    key: 'retenciones10pctNoResidentes',
    filename: '10_NO-RESIDENTES_PETROLERO.pdf',
    category: 'withholding',
    format: 'PDF',
    size: '~260KB'
  },
  {
    key: 'retenciones10pctSectorComun',
    filename: '10_NO-RESIDENTES_SEC.COMUN_.pdf',
    category: 'withholding',
    format: 'PDF',
    size: '~250KB'
  },
  {
    key: 'cuotaMinimaPetrolera',
    filename: 'CUOTA-MIN.FISCAL_PETROLERA.pdf',
    category: 'corporate',
    format: 'PDF',
    size: '~230KB'
  },
  {
    key: 'cuotaMinimaComun',
    filename: 'CUOTA-MIN.FISCAL_SEC.COMUN_.pdf',
    category: 'corporate',
    format: 'PDF',
    size: '~230KB'
  },
  {
    key: 'ivaDestajo',
    filename: 'I.V.A.-DESTAJO.pdf',
    category: 'vat',
    format: 'PDF',
    size: '~240KB'
  },
  {
    key: 'ivaReal',
    filename: 'I.V.A.-REAL.pdf',
    category: 'vat',
    format: 'PDF',
    size: '~250KB'
  },
  {
    key: 'impProdPetrolerosIVS',
    filename: 'IMP.PROD_.PETROLEROS_IVS.pdf',
    category: 'corporate',
    format: 'PDF',
    size: '~240KB'
  },
  {
    key: 'impProdPetroliferosFMI',
    filename: 'IMP.PROD_.PETROLIFEROS_FMI.pdf',
    category: 'corporate',
    format: 'PDF',
    size: '~240KB'
  },
  {
    key: 'impSueldosPetrolero',
    filename: 'IMP.SUELDOS-Y-SALARIOS_PETROLERO.pdf',
    category: 'irpf',
    format: 'PDF',
    size: '~260KB'
  },
  {
    key: 'impSueldosComun',
    filename: 'IMP.SUELDOS-Y-SALARIOS_SEC.COMUN_.pdf',
    category: 'irpf',
    format: 'PDF',
    size: '~260KB'
  },
  {
    key: 'impresoComun',
    filename: 'IMPRESO-COMUN.pdf',
    category: 'general',
    format: 'PDF',
    size: '~220KB'
  },
  {
    key: 'impresoLiquidacion',
    filename: 'IMPRESO-DE-LIQUIDACION.pdf',
    category: 'general',
    format: 'PDF',
    size: '~230KB'
  },
];

// FAQ items
const FAQ_ITEMS = [
  { key: 'faq1' },
  { key: 'faq2' },
  { key: 'faq3' },
  { key: 'faq4' },
  { key: 'faq5' },
  { key: 'faq6' },
];

export default function GuidePage() {
  useParams();
  const t = useTranslations('guidePage');

  const [activeTab, setActiveTab] = useState<TabType>('workflow');
  const [selectedForm, setSelectedForm] = useState(DOWNLOAD_ITEMS[0]);
  const [pdfLoadError, setPdfLoadError] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  // Detect mobile/tablet devices that may not support inline PDF viewing
  useEffect(() => {
    const checkMobile = () => {
      const userAgent = navigator.userAgent.toLowerCase();
      const isMobileDevice = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i.test(userAgent);
      const isSmallScreen = window.innerWidth < 768;
      setIsMobile(isMobileDevice || isSmallScreen);
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Reset error state when form changes
  useEffect(() => {
    setPdfLoadError(false);
  }, [selectedForm]);


  // Get PDF URL
  const getPdfUrl = useCallback((filename: string) => {
    return `/documents/formulaires/${filename}`;
  }, []);

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'irpf':
        return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400';
      case 'corporate':
        return 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400';
      case 'vat':
        return 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400';
      case 'withholding':
        return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400';
      default:
        return 'bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400';
    }
  };

  return (
    <div className="container mx-auto px-4 py-12">
      <Breadcrumb
        items={[{ label: t('title') }]}
        className="mb-6"
      />

      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-4">{t('title')}</h1>
        <p className="text-lg text-muted-foreground">{t('description')}</p>
      </div>

      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as TabType)} className="space-y-6">
        <TabsList className="grid w-full grid-cols-2 lg:grid-cols-4 lg:w-[600px]">
          <TabsTrigger value="workflow" className="gap-2">
            <ClipboardList className="h-4 w-4" />
            <span className="hidden sm:inline">{t('workflowTab')}</span>
            <span className="sm:hidden">{t('workflowTabShort')}</span>
          </TabsTrigger>
          <TabsTrigger value="legislation" className="gap-2">
            <Scale className="h-4 w-4" />
            <span className="hidden sm:inline">{t('legislationTab')}</span>
            <span className="sm:hidden">{t('legislationTabShort')}</span>
          </TabsTrigger>
          <TabsTrigger value="downloads" className="gap-2">
            <Download className="h-4 w-4" />
            <span className="hidden sm:inline">{t('downloadsTab')}</span>
            <span className="sm:hidden">{t('downloadsTabShort')}</span>
          </TabsTrigger>
          <TabsTrigger value="faq" className="gap-2">
            <HelpCircle className="h-4 w-4" />
            <span>FAQ</span>
          </TabsTrigger>
        </TabsList>

        {/* WORKFLOW TAB */}
        <TabsContent value="workflow">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ClipboardList className="h-5 w-5 text-primary" />
                {t('howToDeclaration')}
              </CardTitle>
              <CardDescription>{t('howToDeclarationDesc')}</CardDescription>
            </CardHeader>
            <CardContent>
              {/* Workflow Steps */}
              <div className="space-y-6">
                {WORKFLOW_STEPS.map((step, index) => {
                  const Icon = step.icon;
                  const isLast = index === WORKFLOW_STEPS.length - 1;

                  return (
                    <div key={step.key} className="relative">
                      <div className="flex items-start gap-4">
                        {/* Step number and connector */}
                        <div className="flex flex-col items-center">
                          <div className="flex items-center justify-center w-12 h-12 rounded-full bg-primary text-primary-foreground font-bold text-lg">
                            {index + 1}
                          </div>
                          {!isLast && (
                            <div className="w-0.5 h-16 bg-primary/30 mt-2" />
                          )}
                        </div>

                        {/* Step content */}
                        <div className="flex-1 pb-8">
                          <div className="flex items-center gap-3 mb-2">
                            <Icon className="h-5 w-5 text-primary" />
                            <h3 className="text-lg font-semibold">{t(`${step.key}Title`)}</h3>
                          </div>
                          <p className="text-muted-foreground mb-3">{t(`${step.key}Desc`)}</p>

                          {/* Two-column layout: Tips + Platform Actions */}
                          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                            {/* Tips Column */}
                            <div className="bg-muted/50 p-4 rounded-lg">
                              <p className="text-sm font-medium mb-2">{t('tips')}:</p>
                              <ul className="text-sm text-muted-foreground space-y-1">
                                <li className="flex items-start gap-2">
                                  <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                                  <span>{t(`${step.key}Tip1`)}</span>
                                </li>
                                <li className="flex items-start gap-2">
                                  <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                                  <span>{t(`${step.key}Tip2`)}</span>
                                </li>
                              </ul>
                            </div>

                            {/* Platform Actions Column */}
                            <div className="bg-primary/5 p-4 rounded-lg border border-primary/10">
                              <p className="text-sm font-medium mb-2">{t('platformActions')}:</p>
                              <ul className="text-sm text-muted-foreground space-y-1">
                                <li className="flex items-start gap-2">
                                  <CheckCircle2 className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
                                  <span>{t(`${step.key}Action1`)}</span>
                                </li>
                                <li className="flex items-start gap-2">
                                  <CheckCircle2 className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
                                  <span>{t(`${step.key}Action2`)}</span>
                                </li>
                              </ul>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* LEGISLATION TAB */}
        <TabsContent value="legislation">
          <div className="grid gap-6 md:grid-cols-2">
            {LEGISLATION_ITEMS.map((item) => {
              const Icon = item.icon;
              return (
                <Card key={item.key} className="hover:shadow-lg transition-shadow">
                  <CardHeader>
                    <div className="flex items-start gap-4">
                      <div className="p-3 rounded-lg bg-primary/10">
                        <Icon className="h-6 w-6 text-primary" />
                      </div>
                      <div className="flex-1">
                        <CardTitle className="text-lg">{t(`${item.key}Title`)}</CardTitle>
                        <CardDescription className="mt-1">{t(`${item.key}Desc`)}</CardDescription>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {/* Legislation links */}
                      {item.links.map((link) => {
                        const isAvailable = link.url !== '#';
                        const LinkWrapper = isAvailable ? 'a' : 'div';
                        const linkProps = isAvailable
                          ? {
                              href: link.url,
                              target: '_blank',
                              rel: 'noopener noreferrer',
                            }
                          : {};

                        return (
                          <LinkWrapper
                            key={link.key}
                            {...linkProps}
                            className={`flex items-center justify-between p-3 bg-muted/50 rounded-lg transition-colors ${
                              isAvailable
                                ? 'hover:bg-muted cursor-pointer hover:border-primary/20 border border-transparent'
                                : 'opacity-60 cursor-not-allowed'
                            }`}
                          >
                            <div className="flex items-center gap-2">
                              <BookOpen className="h-4 w-4 text-muted-foreground" />
                              <span className="text-sm">{t(`${item.key}${link.key}`)}</span>
                              {!isAvailable && (
                                <Badge variant="outline" className="text-xs">
                                  {t('comingSoon') || 'Coming soon'}
                                </Badge>
                              )}
                            </div>
                            {isAvailable && <ExternalLink className="h-4 w-4 text-muted-foreground" />}
                          </LinkWrapper>
                        );
                      })}
                    </div>
                    <p className="text-xs text-muted-foreground mt-4 italic">
                      {t('legislationNote')}
                    </p>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </TabsContent>

        {/* DOWNLOADS TAB */}
        <TabsContent value="downloads">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left column - Form list */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5 text-primary" />
                  {t('downloadableFormsTitle')}
                </CardTitle>
                <CardDescription>{t('downloadableFormsDesc')}</CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[600px] pr-4">
                  <div className="space-y-2">
                    {DOWNLOAD_ITEMS.map((item) => (
                      <div
                        key={item.key}
                        onClick={() => setSelectedForm(item)}
                        className={`cursor-pointer p-4 border rounded-lg transition-all hover:border-primary/50 hover:bg-muted/30 ${
                          selectedForm.key === item.key
                            ? 'border-primary bg-primary/5'
                            : ''
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-start gap-3 flex-1">
                            <FileText className={`h-6 w-6 flex-shrink-0 ${
                              selectedForm.key === item.key ? 'text-primary' : 'text-red-500'
                            }`} />
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-sm mb-1">{t(`${item.key}Name`)}</p>
                              <div className="flex items-center gap-2 flex-wrap">
                                <Badge variant="outline" className={getCategoryColor(item.category)}>
                                  {t(`category${item.category.charAt(0).toUpperCase() + item.category.slice(1)}`)}
                                </Badge>
                                <span className="text-xs text-muted-foreground">{item.size}</span>
                              </div>
                            </div>
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            asChild
                            className="flex-shrink-0"
                          >
                            <a
                              href={`/documents/formulaires/${item.filename}`}
                              download
                              onClick={(e) => e.stopPropagation()}
                            >
                              <Download className="h-4 w-4" />
                            </a>
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            {/* Right column - PDF Preview */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5 text-primary" />
                  {t('pdfPreviewTitle')}
                </CardTitle>
                <CardDescription>
                  {t(`${selectedForm.key}Name`)}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {/* PDF Info */}
                  <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className={getCategoryColor(selectedForm.category)}>
                        {t(`category${selectedForm.category.charAt(0).toUpperCase() + selectedForm.category.slice(1)}`)}
                      </Badge>
                      <span className="text-sm text-muted-foreground">{selectedForm.format}</span>
                      <span className="text-sm text-muted-foreground">•</span>
                      <span className="text-sm text-muted-foreground">{selectedForm.size}</span>
                    </div>
                    <Button
                      variant="default"
                      size="sm"
                      asChild
                    >
                      <a
                        href={`/documents/formulaires/${selectedForm.filename}`}
                        download
                      >
                        <Download className="h-4 w-4 mr-2" />
                        {t('downloadButton')}
                      </a>
                    </Button>
                  </div>

                  {/* PDF Preview with fallback for browser compatibility */}
                  <div className="border rounded-lg overflow-hidden bg-gray-50 dark:bg-gray-900">
                    {/* Show fallback UI for mobile devices or when PDF fails to load */}
                    {(isMobile || pdfLoadError) ? (
                      <div className="w-full h-[520px] flex flex-col items-center justify-center p-8 text-center">
                        <div className="bg-primary/10 p-6 rounded-full mb-6">
                          <FileText className="h-16 w-16 text-primary" />
                        </div>
                        <h3 className="text-lg font-semibold mb-2">
                          {t(`${selectedForm.key}Name`)}
                        </h3>
                        <p className="text-sm text-muted-foreground mb-6 max-w-md">
                          {pdfLoadError
                            ? (t('pdfLoadError') || 'Unable to display PDF preview. Please download the file to view it.')
                            : (t('pdfMobileHint') || 'PDF preview is optimized for desktop. Download the file to view on your device.')
                          }
                        </p>
                        <div className="flex flex-col sm:flex-row gap-3">
                          <Button asChild>
                            <a
                              href={getPdfUrl(selectedForm.filename)}
                              download
                            >
                              <Download className="h-4 w-4 mr-2" />
                              {t('downloadButton')}
                            </a>
                          </Button>
                          <Button variant="outline" asChild>
                            <a
                              href={getPdfUrl(selectedForm.filename)}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              <Eye className="h-4 w-4 mr-2" />
                              {t('openInNewTab') || 'Open in new tab'}
                            </a>
                          </Button>
                        </div>
                        {pdfLoadError && (
                          <div className="mt-4 flex items-center gap-2 text-xs text-amber-600 dark:text-amber-400">
                            <AlertTriangle className="h-3 w-3" />
                            <span>{t('browserPdfHint') || 'Your browser may not support inline PDF viewing'}</span>
                          </div>
                        )}
                      </div>
                    ) : (
                      /* Standard iframe for desktop browsers - using iframe which has better browser support */
                      <iframe
                        src={`${getPdfUrl(selectedForm.filename)}#toolbar=1&navpanes=0&scrollbar=1&view=FitH`}
                        className="w-full h-[520px]"
                        title={t(`${selectedForm.key}Name`)}
                        style={{ border: 'none' }}
                      />
                    )}
                  </div>

                  {/* Help text */}
                  <p className="text-xs text-muted-foreground text-center italic">
                    {isMobile
                      ? (t('pdfPreviewHelpMobile') || 'Tap the buttons above to view or download the form')
                      : t('pdfPreviewHelp')
                    }
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* FAQ TAB */}
        <TabsContent value="faq">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <HelpCircle className="h-5 w-5 text-primary" />
                {t('faq')}
              </CardTitle>
              <CardDescription>{t('faqDesc')}</CardDescription>
            </CardHeader>
            <CardContent>
              <Accordion type="single" collapsible className="w-full">
                {FAQ_ITEMS.map((item, index) => (
                  <AccordionItem key={item.key} value={item.key}>
                    <AccordionTrigger className="text-left">
                      <span className="flex items-center gap-3">
                        <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary text-sm flex items-center justify-center">
                          {index + 1}
                        </span>
                        {t(`${item.key}Question`)}
                      </span>
                    </AccordionTrigger>
                    <AccordionContent className="text-muted-foreground pl-9">
                      {t(`${item.key}Answer`)}
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Help CTA */}
      <div className="mt-8 p-6 bg-primary/5 border border-primary/10 rounded-lg text-center">
        <h3 className="text-lg font-semibold mb-2">{t('needMoreHelp')}</h3>
        <p className="text-muted-foreground mb-4">{t('needMoreHelpDesc')}</p>
        <Button
          onClick={() => window.dispatchEvent(new CustomEvent('openChatbot'))}
          className="gap-2"
        >
          <HelpCircle className="h-4 w-4" />
          {t('askAssistant')}
        </Button>
      </div>
    </div>
  );
}
