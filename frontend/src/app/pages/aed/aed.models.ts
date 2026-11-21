import { AED_AVAILABILITY_ORDER } from './aed.constants';

export type AedAvailability = (typeof AED_AVAILABILITY_ORDER)[number];

export interface AedBrief {
  id: string;
  nazwa_obiektu: string;
  adres: string;
  lat: number;
  lon: number;
  dostepnosc: AedAvailability;
  instytucja: string;
}

export interface AedFix {
  message: string;
  before: string;
  after: string;
}

export interface AedDetail extends AedBrief {
  dane: Record<string, string>;
  poprawki: AedFix[];
  zbior: { id: number; tytul: string; slug: string };
}

export interface AedProvinceCharge {
  kod: string;
  nazwa: string;
  gminy: number;
  razem: number;
  procent: number;
}

export interface AedStats {
  liczba_aed: number;
  liczba_instytucji: number;
  dostepnosc: { teraz: Partial<Record<AedAvailability, number>> };
  zbior_ogolnopolski: { id: number; slug: string; tytul: string } | null;
  naladowanie: { gminy: number; gminy_razem: number; procent: number; wojewodztwa: AedProvinceCharge[] };
}
