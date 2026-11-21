import { Routes } from '@angular/router';

import { AedDetailComponent } from './aed-detail.component';
import { AedPageComponent } from './aed-page.component';

export const AED_ROUTES: Routes = [
  { path: '', component: AedPageComponent },
  { path: '!:id', component: AedDetailComponent, data: { breadcrumbs: { translationKey: 'Breadcrumbs.AedDevice' } } },
];
