import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { combineLatest, EMPTY, of } from 'rxjs';
import { catchError, map, switchMap } from 'rxjs/operators';

import { DatasetService } from '@app/services/dataset.service';

import { AedService } from './aed.service';

/** Data for the AED register page, in the shape the DGA register page expects (the same components show both). */
export const aedRegisterResolver = () => {
  const aed = inject(AedService);
  const datasets = inject(DatasetService);
  const router = inject(Router);

  return aed.aggregated().pipe(
    switchMap((resData) =>
      combineLatest([
        datasets.getResourceById(String(resData.resource_id)),
        datasets.getDatasetsStats(String(resData.dataset_id), resData.dataset_slug),
      ]).pipe(map(([resource, stats]) => ({ resData, resource, stats, cms: { body: [] } }))),
    ),
    catchError(() => {
      router.navigate(['/']).then();
      return EMPTY;
    }),
  );
};
