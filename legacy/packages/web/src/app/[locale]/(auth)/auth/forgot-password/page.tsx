'use client'

/**
 * Forgot Password Page
 * Allows users to request a password reset link via email
 * Backend: POST /api/v1/auth/password/reset/request
 */

import { useState } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useToast } from '@/hooks/use-toast'
import { Loader2, Mail, ArrowLeft, CheckCircle } from 'lucide-react'
import Header from '@/components/layout/Header'
import Footer from '@/components/layout/Footer'
import { authApi } from '@/core/api/auth'
import { useLocale, useTranslations } from 'next-intl'

export default function ForgotPasswordPage() {
  const { toast } = useToast()
  const locale = useLocale()
  const t = useTranslations('auth')

  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [emailSent, setEmailSent] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!email) {
      toast({
        variant: 'destructive',
        title: t('emailRequired'),
        description: t('emailRequiredMessage'),
      })
      return
    }

    setIsLoading(true)

    try {
      await authApi.requestPasswordReset({ email })

      setEmailSent(true)
      toast({
        title: t('emailSentSuccess'),
        description: t('emailSentSuccessMessage'),
      })
    } catch (error: unknown) {
      // For security, we always show success message even if email doesn't exist
      setEmailSent(true)
      toast({
        title: t('emailSentSuccess'),
        description: t('emailSentSuccessMessage'),
      })
    } finally {
      setIsLoading(false)
    }
  }

  if (emailSent) {
    return (
      <div className="min-h-screen flex flex-col">
        <Header />

        <main className="flex-1 container mx-auto px-4 py-12">
          <div className="max-w-md mx-auto">
            <Card>
              <CardHeader className="text-center">
                <div className="flex justify-center mb-4">
                  <CheckCircle className="h-16 w-16 text-green-500" />
                </div>
                <CardTitle>{t('emailSentTitle')}</CardTitle>
                <CardDescription>
                  {t('emailSentDescription')}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <p className="text-sm text-blue-800">
                    <strong>{t('emailSentNote')}</strong> {t('emailSentNoteText')}
                  </p>
                </div>

                <Link href={`/${locale}/auth`}>
                  <Button variant="outline" className="w-full">
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    {t('backToLogin')}
                  </Button>
                </Link>
              </CardContent>
            </Card>
          </div>
        </main>

        <Footer />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      <main className="flex-1 container mx-auto px-4 py-12">
        <div className="max-w-md mx-auto">
          <div className="text-center mb-8">
            <div className="flex justify-center mb-4">
              <Mail className="h-16 w-16 text-primary" />
            </div>
            <h1 className="text-4xl font-bold mb-2">{t('forgotPasswordTitle')}</h1>
            <p className="text-muted-foreground">
              {t('forgotPasswordSubtitle')}
            </p>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>{t('forgotPasswordCardTitle')}</CardTitle>
              <CardDescription>
                {t('forgotPasswordCardDescription')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">{t('emailLabel')}</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder={t('emailPlaceholder')}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    disabled={isLoading}
                    autoFocus
                  />
                </div>

                <Button
                  type="submit"
                  className="w-full"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {t('sendingButton')}
                    </>
                  ) : (
                    <>
                      <Mail className="mr-2 h-4 w-4" />
                      {t('sendResetLinkButton')}
                    </>
                  )}
                </Button>

                <div className="pt-4 border-t text-center">
                  <Link href={`/${locale}/auth`} className="text-sm text-primary hover:underline">
                    <ArrowLeft className="inline mr-1 h-3 w-3" />
                    {t('backToLogin')}
                  </Link>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      </main>

      <Footer />
    </div>
  )
}
