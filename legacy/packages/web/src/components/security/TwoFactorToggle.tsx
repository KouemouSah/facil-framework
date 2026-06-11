'use client'

/**
 * Two-Factor Authentication Toggle Component
 * OWASP Compliant - Secure 2FA management with proper validation
 *
 * Features:
 * - Toggle switch to enable/disable 2FA
 * - QR code display for authenticator app setup
 * - Backup codes generation and secure storage warning
 * - Password confirmation for disabling 2FA
 * - TOTP code verification before enabling
 */

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from '@/components/ui/alert'
import { useToast } from '@/hooks/use-toast'
import { Shield, AlertTriangle, CheckCircle2, Copy } from 'lucide-react'
import { authApi2FA } from '@/core/api/auth'
import { getAuthData, update2FAStatus } from '@/core/auth/storage'

interface TwoFactorToggleProps {
  initialEnabled: boolean
  onStatusChange: (enabled: boolean) => void
}

export default function TwoFactorToggle({ initialEnabled, onStatusChange }: TwoFactorToggleProps) {
  const { toast } = useToast()
  const [enabled, setEnabled] = useState(initialEnabled)
  const [loading, setLoading] = useState(false)

  // Enable 2FA modal states
  const [showEnableModal, setShowEnableModal] = useState(false)
  const [qrCodeSVG, setQrCodeSVG] = useState<string>('')
  const [secret, setSecret] = useState<string>('')
  const [backupCodes, setBackupCodes] = useState<string[]>([])
  const [verificationCode, setVerificationCode] = useState('')
  const [step, setStep] = useState<'qr' | 'verify' | 'backup'>('qr')

  // Disable 2FA modal states
  const [showDisableModal, setShowDisableModal] = useState(false)
  const [password, setPassword] = useState('')

  /**
   * Handle toggle switch change
   * OWASP: Multi-step verification before enabling sensitive features
   */
  const handleToggle = async (checked: boolean) => {
    if (checked) {
      // Enable 2FA - show setup modal
      await startEnable2FA()
    } else {
      // Disable 2FA - show password confirmation
      setShowDisableModal(true)
    }
  }

  /**
   * Start 2FA enable process
   * Step 1: Generate QR code and backup codes
   */
  const startEnable2FA = async () => {
    setLoading(true)
    try {
      const authData = getAuthData()
      if (!authData) {
        throw new Error('Non authentifié')
      }

      const response = await authApi2FA.enable(authData.access_token)

      setQrCodeSVG(response.qr_code_svg)
      setSecret(response.secret)
      setBackupCodes(response.backup_codes)
      setStep('qr')
      setShowEnableModal(true)
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Erreur',
        description: error instanceof Error ? error.message : 'Impossible d\'activer 2FA',
      })
    } finally {
      setLoading(false)
    }
  }

  /**
   * Verify 2FA setup with TOTP code
   * Step 2: User enters code from authenticator app
   * OWASP: Verify TOTP before saving to prevent misconfiguration
   */
  const verifyEnable2FA = async () => {
    if (verificationCode.length !== 6) {
      toast({
        variant: 'destructive',
        title: 'Code invalide',
        description: 'Le code doit contenir 6 chiffres',
      })
      return
    }

    setLoading(true)
    try {
      const authData = getAuthData()
      if (!authData) {
        throw new Error('Non authentifié')
      }

      await authApi2FA.verifySetup(authData.access_token, {
        secret,
        code: verificationCode,
        backup_codes: backupCodes,
      })

      setStep('backup')
      toast({
        title: '2FA activé',
        description: 'L\'authentification à deux facteurs est maintenant active',
      })
      setEnabled(true)
      onStatusChange(true)
      // IMPORTANT: Update localStorage to persist 2FA status
      update2FAStatus(true)
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Code incorrect',
        description: error instanceof Error ? error.message : 'Vérifiez le code et réessayez',
      })
    } finally {
      setLoading(false)
    }
  }

  /**
   * Disable 2FA with password confirmation
   * OWASP: Require password before disabling security features
   */
  const confirmDisable2FA = async () => {
    if (!password) {
      toast({
        variant: 'destructive',
        title: 'Mot de passe requis',
        description: 'Entrez votre mot de passe pour désactiver 2FA',
      })
      return
    }

    setLoading(true)
    try {
      const authData = getAuthData()
      if (!authData) {
        throw new Error('Non authentifié')
      }

      await authApi2FA.disable(authData.access_token, password)

      setEnabled(false)
      onStatusChange(false)
      setShowDisableModal(false)
      setPassword('')
      // IMPORTANT: Update localStorage to persist 2FA status
      update2FAStatus(false)
      toast({
        title: '2FA désactivé',
        description: 'L\'authentification à deux facteurs est maintenant désactivée',
      })
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Erreur',
        description: error instanceof Error ? error.message : 'Mot de passe incorrect',
      })
    } finally {
      setLoading(false)
    }
  }

  /**
   * Copy backup codes to clipboard
   */
  const copyBackupCodes = () => {
    navigator.clipboard.writeText(backupCodes.join('\n'))
    toast({
      title: 'Copié',
      description: 'Codes de secours copiés dans le presse-papier',
    })
  }

  /**
   * Close enable modal and reset state
   */
  const closeEnableModal = () => {
    setShowEnableModal(false)
    setQrCodeSVG('')
    setSecret('')
    setBackupCodes([])
    setVerificationCode('')
    setStep('qr')
  }

  return (
    <>
      {/* Toggle Switch */}
      <div className="flex items-center justify-between space-x-2">
        <div className="flex items-center space-x-2">
          <Shield className="h-5 w-5 text-primary" />
          <div>
            <Label htmlFor="2fa-toggle" className="text-base font-medium cursor-pointer">
              Authentification à deux facteurs (2FA)
            </Label>
            <p className="text-sm text-muted-foreground">
              {enabled
                ? 'Protection active - Code requis à chaque connexion'
                : 'Ajoutez une couche de sécurité supplémentaire'}
            </p>
          </div>
        </div>
        <Switch
          id="2fa-toggle"
          checked={enabled}
          onCheckedChange={handleToggle}
          disabled={loading}
        />
      </div>

      {/* Enable 2FA Modal */}
      <Dialog open={showEnableModal} onOpenChange={setShowEnableModal}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              Activer l&apos;authentification à deux facteurs
            </DialogTitle>
            <DialogDescription>
              {step === 'qr' && 'Scannez le code QR avec votre application d\'authentification'}
              {step === 'verify' && 'Entrez le code à 6 chiffres de votre application'}
              {step === 'backup' && 'Sauvegardez ces codes de secours en lieu sûr'}
            </DialogDescription>
          </DialogHeader>

          {/* Step 1: QR Code */}
          {step === 'qr' && (
            <div className="space-y-4">
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Applications recommandées</AlertTitle>
                <AlertDescription>
                  Google Authenticator, Authy, Microsoft Authenticator
                </AlertDescription>
              </Alert>

              <div className="flex justify-center p-4 bg-white rounded-lg">
                <div dangerouslySetInnerHTML={{ __html: qrCodeSVG }} />
              </div>

              <div className="text-center text-sm text-muted-foreground">
                ou entrez ce code manuellement : <code className="font-mono">{secret}</code>
              </div>

              <Button className="w-full" onClick={() => setStep('verify')}>
                J&apos;ai scanné le QR code
              </Button>
            </div>
          )}

          {/* Step 2: Verification Code */}
          {step === 'verify' && (
            <div className="space-y-4">
              <div>
                <Label htmlFor="verification-code">Code de vérification</Label>
                <Input
                  id="verification-code"
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="123456"
                  value={verificationCode}
                  onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, ''))}
                  className="text-center text-2xl tracking-widest"
                />
              </div>

              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setStep('qr')} className="w-full">
                  Retour
                </Button>
                <Button onClick={verifyEnable2FA} disabled={loading} className="w-full">
                  {loading ? 'Vérification...' : 'Vérifier'}
                </Button>
              </div>
            </div>
          )}

          {/* Step 3: Backup Codes */}
          {step === 'backup' && (
            <div className="space-y-4">
              <Alert>
                <CheckCircle2 className="h-4 w-4" />
                <AlertTitle>2FA activé avec succès!</AlertTitle>
                <AlertDescription>
                  Sauvegardez ces codes de secours. Vous pouvez les utiliser si vous perdez l&apos;accès à votre application d&apos;authentification.
                </AlertDescription>
              </Alert>

              <div className="p-4 bg-muted rounded-lg space-y-1 font-mono text-sm">
                {backupCodes.map((code, index) => (
                  <div key={index}>{code}</div>
                ))}
              </div>

              <Button variant="outline" onClick={copyBackupCodes} className="w-full">
                <Copy className="mr-2 h-4 w-4" />
                Copier les codes
              </Button>

              <Button onClick={closeEnableModal} className="w-full">
                J&apos;ai sauvegardé mes codes
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Disable 2FA Modal */}
      <Dialog open={showDisableModal} onOpenChange={setShowDisableModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Désactiver l&apos;authentification à deux facteurs</DialogTitle>
            <DialogDescription>
              Entrez votre mot de passe pour confirmer la désactivation. Cela réduira la sécurité de votre compte.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Attention</AlertTitle>
              <AlertDescription>
                Votre compte sera moins sécurisé sans 2FA
              </AlertDescription>
            </Alert>

            <div>
              <Label htmlFor="password">Mot de passe</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Entrez votre mot de passe"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowDisableModal(false)
                setPassword('')
              }}
            >
              Annuler
            </Button>
            <Button variant="destructive" onClick={confirmDisable2FA} disabled={loading}>
              {loading ? 'Désactivation...' : 'Désactiver 2FA'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
