import { DOCUMENT } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Inject, Injectable } from '@angular/core';
import { Observable, map, shareReplay } from 'rxjs';

import { AedBrief, AedDetail, AedNearest, AedStats } from './aed.models';

interface ApiResponse<T> {
  data: T;
}

@Injectable({ providedIn: 'root' })
export class AedService {
  private readonly base = '/api/aed';

  readonly stats$: Observable<AedStats> = this.http.get<ApiResponse<AedStats>>(`${this.base}/stats`).pipe(
    map((r) => r.data),
    shareReplay(1),
  );

  constructor(
    private readonly http: HttpClient,
    @Inject(DOCUMENT) private readonly document: Document,
  ) {}

  list(at?: string): Observable<AedBrief[]> {
    return this.http.get<ApiResponse<AedBrief[]>>(this.base, { params: at ? { at } : {} }).pipe(map((r) => r.data));
  }

  /** Nearest AED available at `at` (now when empty) for an address or a point. */
  nearest(where: { address: string } | { lat: number; lon: number }, at?: string): Observable<AedNearest> {
    const params: Record<string, string> = Object.fromEntries(Object.entries(where).map(([k, v]) => [k, String(v)]));
    if (at) {
      params['at'] = at;
    }
    return this.http.get<AedNearest>(`${this.base}/nearest`, { params });
  }

  nearestApiUrl(lat: number, lon: number, at?: string): string {
    return `${this.base}/nearest?lat=${lat.toFixed(5)}&lon=${lon.toFixed(5)}${at ? '&at=' + at : ''}`;
  }

  detail(id: string): Observable<AedDetail> {
    return this.http.get<ApiResponse<AedDetail>>(`${this.base}/${encodeURIComponent(id)}`).pipe(map((r) => r.data));
  }

  reportIssue(datasetId: number, comment: string): Observable<unknown> {
    return this.http.post(`/api/1.4/datasets/${datasetId}/comments`, {
      data: { type: 'comment', attributes: { comment } },
    });
  }

  /** The provider panel runs on the admin. subdomain of the same portal. */
  adminUrl(path: string): string {
    const location = this.document.defaultView?.location;
    if (!location) {
      return path;
    }
    return `${location.protocol}//admin.${location.host.replace(/^www\./, '')}${path}`;
  }
}
