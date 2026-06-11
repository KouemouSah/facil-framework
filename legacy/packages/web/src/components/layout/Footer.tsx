'use client';

import Link from 'next/link';
import Image from 'next/image';
import { useLocale, useTranslations } from 'next-intl';
import { Mail, Phone, MapPin } from 'lucide-react';

const Footer = () => {
  const locale = useLocale();
  const t = useTranslations('footer');
  const tNav = useTranslations('nav');

  return (
    <footer className="border-t bg-muted/30">
      <div className="container mx-auto px-4 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* About */}
          <div className="space-y-4">
            <div className="flex items-center space-x-3">
              <Image src="/logo.png" alt="Facil Logo" width={114} height={48} className="h-12 w-auto" />
            </div>
            <p className="text-sm text-muted-foreground">{t('description')}</p>
          </div>

          {/* Services */}
          <div>
            <h3 className="font-semibold mb-4">{t('services')}</h3>
            <ul className="space-y-2 text-sm">
              <li>
                <Link
                  href={`/${locale}/services`}
                  className="text-muted-foreground hover:text-primary transition-colors"
                >
                  {t('allServices')}
                </Link>
              </li>
              <li>
                <Link
                  href={`/${locale}/ministere`}
                  className="text-muted-foreground hover:text-primary transition-colors"
                >
                  {tNav('ministries')}
                </Link>
              </li>
              <li>
                <Link
                  href={`/${locale}/calculateur`}
                  className="text-muted-foreground hover:text-primary transition-colors"
                >
                  {tNav('calculator')}
                </Link>
              </li>
              <li>
                <Link
                  href={`/${locale}/guide`}
                  className="text-muted-foreground hover:text-primary transition-colors"
                >
                  {t('practicalGuide')}
                </Link>
              </li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h3 className="font-semibold mb-4">{t('legal')}</h3>
            <ul className="space-y-2 text-sm">
              <li>
                <Link
                  href={`/${locale}/legal/privacy`}
                  className="text-muted-foreground hover:text-primary transition-colors"
                >
                  {t('privacy')}
                </Link>
              </li>
              <li>
                <Link
                  href={`/${locale}/legal/terms`}
                  className="text-muted-foreground hover:text-primary transition-colors"
                >
                  {t('terms')}
                </Link>
              </li>
              <li>
                <Link
                  href={`/${locale}/legal/cookies`}
                  className="text-muted-foreground hover:text-primary transition-colors"
                >
                  {t('cookies')}
                </Link>
              </li>
            </ul>
          </div>

          {/* Contact */}
          <div>
            <h3 className="font-semibold mb-4">{t('contactTitle')}</h3>
            <ul className="space-y-3 text-sm">
              <li className="flex items-start space-x-2 text-muted-foreground">
                <MapPin className="h-4 w-4 mt-0.5 flex-shrink-0" />
                <span>{t('address')}</span>
              </li>
              <li className="flex items-center space-x-2 text-muted-foreground">
                <Phone className="h-4 w-4 flex-shrink-0" />
                <span>{t('phone')}</span>
              </li>
              <li className="flex items-center space-x-2 text-muted-foreground">
                <Mail className="h-4 w-4 flex-shrink-0" />
                <span>{t('email')}</span>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-8 pt-8 border-t text-center text-sm text-muted-foreground">
          <p>{t('copyright', { year: new Date().getFullYear() })}</p>
        </div>
      </div>
    </footer>
  );
};

export { Footer };
export default Footer;
