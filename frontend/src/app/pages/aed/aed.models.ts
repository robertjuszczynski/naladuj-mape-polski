import { AED_AVAILABILITY_ORDER } from './aed.constants';

export type AedAvailability = (typeof AED_AVAILABILITY_ORDER)[number];

export interface AedBrief {
  id: string;
  name: string;
  address: string;
  lat: number;
  lon: number;
  availability: AedAvailability;
  institution: string;
}

export interface AedFix {
  message: string;
  before: string;
  after: string;
}

export interface AedDetail extends AedBrief {
  fields: Record<string, string>;
  fixes: AedFix[];
  dataset: { id: number; title: string; slug: string };
}

export interface AedProvinceCoverage {
  code: string;
  name: string;
  municipalities: number;
  total: number;
  percent: number;
}

export interface AedStats {
  aed_count: number;
  institution_count: number;
  availability: { now: Partial<Record<AedAvailability, number>> };
  national_dataset: { id: number; slug: string; title: string } | null;
  coverage: { municipalities: number; municipalities_total: number; percent: number; provinces: AedProvinceCoverage[] };
}

export interface AedNearby extends AedBrief {
  distance_m: number;
  walk_min: number;
  opening_hours: string;
  opens_at: string | null;
  phrase: string;
}

export interface AedIncidentPoint {
  lat: number;
  lon: number;
  label: string;
  exact: boolean;
}

export interface AedNearest {
  meta: { at: string; point: AedIncidentPoint; radius_km: number };
  data: { open: AedNearby[]; closed: AedNearby[]; unknown: AedNearby[] };
}
