export interface DirectoryCompany {
  id: string;
  legal_name: string;
  nif?: string;
  registration_number?: string;
  sector_actividad?: string;
  subsector_actividad?: string;
  city_name?: string;
  provincia?: string;
  address?: string;
  forma_juridica?: string;
  objeto_social?: string;
  zone_code?: string;
  zone_tier?: string;
}

export interface DirectorySearchResponse {
  items: DirectoryCompany[];
  total: number;
  page: number;
  page_size: number;
}

export interface FilterOption {
  value: string;
  label: string;
  count?: number;
}
