/**
 * commitlint config — Facil Framework
 * https://commitlint.js.org/reference/configuration
 *
 * Enforces Conventional Commits with project-specific scopes.
 */
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      [
        'feat',     // new feature
        'fix',      // bug fix
        'docs',     // documentation only
        'style',    // formatting, no code change
        'refactor', // code restructure, no behavior change
        'perf',     // performance improvement
        'test',     // tests only
        'build',    // build system / external deps
        'ci',       // CI/CD changes
        'chore',    // tooling, deps, no production code
        'revert',   // revert previous commit
      ],
    ],
    'scope-enum': [
      1, // warning, not error — allows new scopes
      'always',
      [
        'backend',
        'frontend',
        'mobile',
        'inspector',
        'studio',
        'workflow',
        'auth',
        'rbac',
        'modules',
        'profiles',
        'docs',
        'wiki',
        'ci',
        'deps',
        'security',
        'release',
        'agents',
        // Socle de déploiement : le repo a désormais un répertoire infra/ (chart
        // Helm k3s) et un moteur deploy/ (providers, bootstrap). 'helm'/'deploy'
        // étaient déjà utilisés par une trentaine de commits sans figurer ici.
        'infra',
        'deploy',
        'helm',
        'phase-A.5',
        'phase-B',
        'phase-B.5',
        'phase-B.6',
        'phase-C',
        'phase-D',
        'phase-E',
        'phase-F',
        'phase-G',
        'phase-H',
        'phase-H.5',
        'phase-I',
        'phase-I.bis',
        'phase-J',
        'phase-K',
        'phase-L',
        'phase-M',
        'phase-N',
        'phase-N.5',
        'repo',
      ],
    ],
    'subject-case': [2, 'never', ['upper-case', 'pascal-case']],
    'subject-empty': [2, 'never'],
    'subject-full-stop': [2, 'never', '.'],
    'header-max-length': [2, 'always', 100],
    'body-max-line-length': [1, 'always', 120],
    'footer-leading-blank': [2, 'always'],
    'body-leading-blank': [2, 'always'],
  },
};
