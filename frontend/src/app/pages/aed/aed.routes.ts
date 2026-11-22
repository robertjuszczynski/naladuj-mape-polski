import { Routes } from '@angular/router';

import { DgaInformationPointTablePageComponent } from '@app/pages/dga-information-point/dga-information-point-table-page/dga-information-point-table-page.component';
import { DgaInformationPointTableComponent } from '@app/pages/dga-information-point/dga-information-point-table/dga-information-point-table.component';

import { AedDetailComponent } from './aed-detail.component';
import { AedPageComponent } from './aed-page.component';
import { aedRegisterResolver } from './aed-register.resolver';

export const AED_ROUTES: Routes = [
  { path: '', component: AedPageComponent },
  {
    path: '!wykaz',
    component: DgaInformationPointTablePageComponent,
    data: { breadcrumbs: { translationKey: 'Breadcrumbs.AedRegister' } },
    resolve: { post: aedRegisterResolver },
    children: [
      { path: '', redirectTo: '!table', pathMatch: 'full' },
      { path: '!table', component: DgaInformationPointTableComponent },
    ],
  },
  { path: '!:id', component: AedDetailComponent, data: { breadcrumbs: { translationKey: 'Breadcrumbs.AedDevice' } } },
];
