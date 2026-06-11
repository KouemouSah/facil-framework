/** @type {import('next-sitemap').IConfig} */
module.exports = {
  siteUrl: process.env.NEXT_PUBLIC_SITE_URL || 'https://taxasge.gq',
  generateRobotsTxt: true,
  exclude: ['/api/*', '/dashboard/*', '/auth/*'],
  alternateRefs: [
    {
      href: 'https://taxasge.gq/es',
      hreflang: 'es',
    },
    {
      href: 'https://taxasge.gq/fr',
      hreflang: 'fr',
    },
    {
      href: 'https://taxasge.gq/en',
      hreflang: 'en',
    },
  ],
  robotsTxtOptions: {
    policies: [
      {
        userAgent: '*',
        allow: '/',
        disallow: ['/api/', '/dashboard/', '/auth/'],
      },
    ],
  },
};
