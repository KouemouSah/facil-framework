/**
 * Inspector Color Palette
 *
 * Blue professional theme (vs green citizen Facil).
 * Material Design 3 compliant.
 */

export const inspectorColors = {
  primary: {
    main: '#1565C0',
    dark: '#0D47A1',
    light: '#42A5F5',
    container: '#D1E4FF',
    onContainer: '#001D36',
    contrast: '#FFFFFF',
  },
  secondary: {
    main: '#455A64',
    dark: '#263238',
    light: '#78909C',
    container: '#CFD8DC',
  },
  tertiary: {
    main: '#00838F',
    dark: '#006064',
    light: '#4DD0E1',
  },
  status: {
    inProgress: '#F57F17',
    conforme: '#2E7D32',
    nonConforme: '#C62828',
    miseEnDemeure: '#E65100',
    sealProposed: '#6A1B9A',
    sealApproved: '#B71C1C',
    sealRejected: '#4E342E',
    completed: '#1B5E20',
    cancelled: '#616161',
  },
  background: '#FAFAFA',
  surface: '#FFFFFF',
  surfaceVariant: '#ECEFF1',
  error: '#B00020',
  text: {
    primary: '#212121',
    secondary: '#616161',
    disabled: '#9E9E9E',
    inverse: '#FFFFFF',
  },
  divider: '#E0E0E0',
  elevation: {
    level0: '#FFFFFF',
    level1: '#F5F5F5',
    level2: '#EEEEEE',
  },
} as const;

export const inspectorColorsDark = {
  primary: {
    main: '#90CAF9',
    dark: '#42A5F5',
    light: '#BBDEFB',
    container: '#004B87',
    onContainer: '#D1E4FF',
    contrast: '#003258',
  },
  secondary: {
    main: '#B0BEC5',
    dark: '#78909C',
    light: '#CFD8DC',
    container: '#37474F',
  },
  status: {
    inProgress: '#FFD54F',
    conforme: '#66BB6A',
    nonConforme: '#EF5350',
    miseEnDemeure: '#FF9800',
    sealProposed: '#CE93D8',
    sealApproved: '#EF5350',
    sealRejected: '#8D6E63',
    completed: '#4CAF50',
    cancelled: '#9E9E9E',
  },
  background: '#121212',
  surface: '#1E1E1E',
  surfaceVariant: '#263238',
  error: '#CF6679',
  text: {
    primary: '#FFFFFF',
    secondary: '#B0BEC5',
    disabled: '#616161',
    inverse: '#121212',
  },
  divider: '#37474F',
  tertiary: {
    main: '#4DD0E1',
    dark: '#00838F',
    light: '#80DEEA',
  },
  elevation: {
    level0: '#1E1E1E',
    level1: '#262626',
    level2: '#2E2E2E',
  },
} as const;
