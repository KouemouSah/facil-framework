'use client'

/**
 * Password Reset Request Page
 * Allows users to request a password reset email
 * Backend: POST /auth/password/reset/request
 */

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useToast } from "@/hooks/use-toast"
import { Loader2, Mail, ArrowLeft } from "lucide-react"
import Header from "@/components/layout/Header"
import Footer from "@/components/layout/Footer"
import { authApi } from "@/core/api/auth"
import { useLocale, useTranslations } from 'next-intl'

export default function ResetPasswordPage() {
  const router = useRouter()
  const { toast } = useToast()
  const locale = useLocale()
  const t = useTranslations('auth')

  const [email, setEmail] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [emailSent, setEmailSent] = useState(false)

  const handleRequestReset = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      const result = await authApi.requestPasswordReset({ email })

      setEmailSent(true)
      toast({
        title: t('emailSentSuccess'),
        description: t('codeResentMessage', { email: result.email }),
      })
    } catch (error: unknown) {
      toast({
        variant: "destructive",
        title: t('resendError'),
        description: error instanceof Error ? error.message : t('resendErrorMessage'),
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
            <div className="text-center mb-8">
              <div className="flex justify-center mb-4">
                <div className="h-16 w-16 bg-primary/10 rounded-full flex items-center justify-center">
                  <Mail className="h-8 w-8 text-primary" />
                </div>
              </div>
              <h1 className="text-4xl font-bold mb-2">{t('checkEmailTitle')}</h1>
              <p className="text-muted-foreground">
                {t('checkEmailSubtitle', { email })}
              </p>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>{t('nextStepsTitle')}</CardTitle>
                <CardDescription>
                  {t('nextStepsDescription')}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2 text-sm">
                  <p>{t('step1')}</p>
                  <p>{t('step2')}</p>
                  <p>{t('step3')}</p>
                </div>

                <div className="pt-4 space-y-2">
                  <p className="text-sm text-muted-foreground text-center">
                    {t('linkExpiry')}
                  </p>

                  <Button
                    variant="outline"
                    onClick={() => setEmailSent(false)}
                    className="w-full"
                  >
                    {t('resendEmail')}
                  </Button>

                  <Button
                    variant="link"
                    onClick={() => router.push(`/${locale}/auth`)}
                    className="w-full"
                  >
                    {t('backToLogin')}
                  </Button>
                </div>
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
            <h1 className="text-4xl font-bold mb-2">{t('resetPasswordTitle')}</h1>
            <p className="text-muted-foreground">
              {t('resetPasswordSubtitle')}
            </p>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>{t('resetPasswordCardTitle')}</CardTitle>
              <CardDescription>
                {t('resetPasswordCardDescription')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleRequestReset} className="space-y-4">
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
                      {t('sendLinkButton')}
                    </>
                  )}
                </Button>

                <div className="text-center pt-2">
                  <Link href={`/${locale}/auth`}>
                    <Button variant="link" className="text-sm">
                      <ArrowLeft className="mr-2 h-4 w-4" />
                      {t('backToLogin')}
                    </Button>
                  </Link>
                </div>
              </form>
            </CardContent>
          </Card>

          <div className="mt-6 text-center">
            <p className="text-sm text-muted-foreground">
              {t('rememberPassword')}{" "}
              <Link href={`/${locale}/auth`} className="text-primary hover:underline">
                {t('loginLink')}
              </Link>
            </p>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  )
}
