import { AsyncPipe, NgFor, NgIf } from '@angular/common';
import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { LocalizeRouterPipe } from '@gilsdav/ngx-translate-router';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { EMPTY, catchError, map, switchMap } from 'rxjs';

import { AED_ROUTE } from './aed.constants';
import { AedBrief, AedDetail } from './aed.models';
import { AedService } from './aed.service';
import { AedMapComponent } from './aed-map.component';

const SHOWN_FIELDS = [
  'opis_lokalizacji',
  'pietro',
  'wewnatrz_budynku',
  'dostep',
  'godziny_dostepnosci',
  'sprawny',
  'data_ostatniego_przegladu',
  'producent',
  'dysponent_nazwa',
  'dysponent_telefon',
  'kod_teryt_gminy',
  'data_aktualizacji',
];
const REPORT_TYPES = ['not_working', 'inaccessible', 'no_device', 'wrong_location', 'other'];

@Component({
  selector: 'app-aed-detail',
  standalone: true,
  imports: [NgIf, NgFor, AsyncPipe, FormsModule, RouterLink, LocalizeRouterPipe, TranslatePipe, AedMapComponent],
  templateUrl: './aed-detail.component.html',
  styleUrls: ['./aed-detail.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AedDetailComponent {
  readonly route = AED_ROUTE;
  readonly shown = SHOWN_FIELDS;
  readonly reportTypes = REPORT_TYPES;
  readonly loadError = signal(false);
  readonly reportError = signal('');
  readonly sent = signal(false);
  readonly sending = signal(false);
  reportType = '';
  reportText = '';

  readonly vm$ = this.activatedRoute.paramMap.pipe(
    map((params) => params.get('id') ?? ''),
    switchMap((id) =>
      this.service.detail(id).pipe(
        map((aed) => ({ aed, points: [aed] as AedBrief[], center: [aed.lat, aed.lon] as [number, number] })),
        catchError(() => {
          this.loadError.set(true);
          return EMPTY;
        }),
      ),
    ),
  );

  constructor(
    private readonly activatedRoute: ActivatedRoute,
    private readonly service: AedService,
    private readonly translate: TranslateService,
  ) {}

  value(raw: string | undefined): string {
    if (raw === 'true') {
      return this.translate.instant('Aed.Yes');
    }
    if (raw === 'false') {
      return this.translate.instant('Aed.No');
    }
    return raw || '';
  }

  submit(aed: AedDetail): void {
    if (!this.reportType) {
      this.reportError.set('Aed.ReportPick');
      return;
    }
    const comment = this.translate.instant('Aed.ReportComment', {
      id: aed.id,
      name: aed.name,
      address: aed.address,
      problem: this.translate.instant('Aed.Report.' + this.reportType),
      text: this.reportText ? ` ${this.reportText}` : '',
    });
    this.sending.set(true);
    this.service.reportIssue(aed.dataset.id, comment).subscribe({
      next: () => {
        this.sent.set(true);
        this.reportError.set('');
        this.sending.set(false);
      },
      error: () => {
        this.reportError.set('Aed.ReportError');
        this.sending.set(false);
      },
    });
  }
}
