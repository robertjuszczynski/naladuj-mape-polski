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
