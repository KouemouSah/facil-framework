/**
 * Public surface of the companies feature module.
 */

export * from './types/companies.types';
export * as companiesApi from './services/companies-api';
export {
  useCompaniesList,
  useCompanyDetail,
  useCreateCompany,
  useUpdateCompany,
  useDeleteCompany,
  useCompanyMembers,
  useCompanyMembership,
  useAddMember,
  useUpdateMemberRole,
  useRemoveMember,
  useDownloadLicensePdf,
  useArchiveCompany,
  isArchiveBlockedError,
  getArchiveBlockers,
} from './services/companies-hooks';
export type {
  CompanyMembershipPermissions,
  ArchiveBlockers,
} from './services/companies-hooks';
export { downloadLicensePdf } from './services/company-pdf';
