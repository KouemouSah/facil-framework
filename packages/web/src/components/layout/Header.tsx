'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { useLocale, useTranslations } from 'next-intl';
import { Search, Menu, X, MessageCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import LanguageSwitcher from '@/components/shared/LanguageSwitcher';

const Header = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const locale = useLocale();
  const router = useRouter();
  const t = useTranslations('nav');

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto px-4">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <Link href={`/${locale}`} className="flex items-center space-x-3">
            <Image src="/logo.png" alt="Facil Logo" width={114} height={48} className="h-12 w-auto" />
          </Link>

          {/* Desktop Navigation — order: Servicios, Licencias, Empresas, Ministerios, Calculadora, Guía */}
          <nav className="hidden md:flex items-center space-x-6">
            <Link href={`/${locale}/services`} className="text-sm font-medium text-foreground hover:text-primary transition-colors">
              {t('services')}
            </Link>
            <Link href={`/${locale}/licencias-comerciales`} className="text-sm font-medium text-foreground hover:text-primary transition-colors">
              {t('licenses')}
            </Link>
            <Link href={`/${locale}/annuaire`} className="text-sm font-medium text-foreground hover:text-primary transition-colors">
              {t('directory')}
            </Link>
            <Link href={`/${locale}/ministere`} className="text-sm font-medium text-foreground hover:text-primary transition-colors">
              {t('ministries')}
            </Link>
            <Link href={`/${locale}/calculateur`} className="text-sm font-medium text-foreground hover:text-primary transition-colors">
              {t('calculator')}
            </Link>
            <Link href={`/${locale}/guide`} className="text-sm font-medium text-foreground hover:text-primary transition-colors">
              {t('guide')}
            </Link>
            <Link href={`/${locale}/chat`} className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:text-primary/80 transition-colors">
              <MessageCircle className="w-4 h-4" />
              {t('chat')}
            </Link>
          </nav>

          {/* Actions */}
          <div className="flex items-center space-x-2">
            <Button
              variant="ghost"
              size="icon"
              className="hidden lg:inline-flex"
              aria-label="Search services"
              onClick={() => router.push(`/${locale}/services`)}
            >
              <Search className="h-5 w-5" />
            </Button>
            <LanguageSwitcher />
            <Link href={`/${locale}/auth`}>
              <Button className="hidden sm:inline-flex">{t('login')}</Button>
            </Link>

            {/* Mobile Menu Toggle */}
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={mobileMenuOpen}
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </Button>
          </div>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden py-4 animate-fade-in">
            <nav className="flex flex-col space-y-3">
              <Link
                href={`/${locale}/services`}
                className="text-sm font-medium text-foreground hover:text-primary transition-colors px-2 py-1"
                onClick={() => setMobileMenuOpen(false)}
              >
                {t('services')}
              </Link>
              <Link
                href={`/${locale}/licencias-comerciales`}
                className="text-sm font-medium text-foreground hover:text-primary transition-colors px-2 py-1"
                onClick={() => setMobileMenuOpen(false)}
              >
                {t('licenses')}
              </Link>
              <Link href={`/${locale}/annuaire`} className="text-sm font-medium text-foreground hover:text-primary transition-colors px-2 py-1" onClick={() => setMobileMenuOpen(false)}>
                {t('directory')}
              </Link>
              <Link href={`/${locale}/ministere`} className="text-sm font-medium text-foreground hover:text-primary transition-colors px-2 py-1" onClick={() => setMobileMenuOpen(false)}>
                {t('ministries')}
              </Link>
              <Link href={`/${locale}/calculateur`} className="text-sm font-medium text-foreground hover:text-primary transition-colors px-2 py-1" onClick={() => setMobileMenuOpen(false)}>
                {t('calculator')}
              </Link>
              <Link href={`/${locale}/guide`} className="text-sm font-medium text-foreground hover:text-primary transition-colors px-2 py-1" onClick={() => setMobileMenuOpen(false)}>
                {t('guide')}
              </Link>
              <Link href={`/${locale}/chat`} className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:text-primary/80 transition-colors px-2 py-1" onClick={() => setMobileMenuOpen(false)}>
                <MessageCircle className="w-4 h-4" />
                {t('chat')}
              </Link>
              <div className="pt-2">
                <Link href={`/${locale}/auth`} className="block">
                  <Button className="w-full" onClick={() => setMobileMenuOpen(false)}>
                    {t('login')}
                  </Button>
                </Link>
              </div>
            </nav>
          </div>
        )}
      </div>
    </header>
  );
};

export { Header };
export default Header;
