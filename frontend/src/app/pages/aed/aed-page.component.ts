import { AsyncPipe, DOCUMENT, NgFor, NgIf } from '@angular/common';
import { ChangeDetectionStrategy, Component, Inject, OnInit, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { LocalizeRouterPipe, LocalizeRouterService } from '@gilsdav/ngx-translate-router';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import type { LatLngTuple } from 'leaflet';
import { finalize } from 'rxjs';

import { AedMarkComponent } from '@app/shared/aed-mark/aed-mark.component';

import {
  AED_AVAILABILITY_ORDER,
  AED_PAGE_SIZE,
  AED_PAGE_STEP,
  AED_ROUTE,
  AED_SCOPE_PATH,
  AED_TEMPLATE_PATH,
  AED_WIZARD_PATH,
} from './aed.constants';
import { AedAvailability, AedBrief } from './aed.models';
import { AedService } from './aed.service';
import { AedMapComponent } from './aed-map.component';
import { AedNumberPipe } from './aed-number.pipe';

type TimeMode = 'now' | 'chosen';

const BATTERY_INNER_WIDTH = 182;
const BATTERY_MIN_PERCENT = 3;

@Component({
  selector: 'app-aed-page',
  standalone: true,
  imports: [
    NgIf,
    NgFor,
    AsyncPipe,
    FormsModule,
    RouterLink,
    LocalizeRouterPipe,
    TranslatePipe,
    AedMapComponent,
    AedMarkComponent,
    AedNumberPipe,
  ],
  templateUrl: './aed-page.component.html',
  styleUrls: ['./aed-page.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AedPageComponent implements OnInit {
  readonly route = AED_ROUTE;
  readonly order = AED_AVAILABILITY_ORDER;
  readonly days = [0, 1, 2, 3, 4, 5, 6];
  readonly stats$ = this.aed.stats$;
  readonly wizardUrl = this.aed.adminUrl(AED_WIZARD_PATH);
  readonly templateUrl = this.aed.adminUrl(AED_TEMPLATE_PATH);
  readonly scopeUrl = this.aed.adminUrl(AED_SCOPE_PATH);

  readonly points = signal<AedBrief[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly query = signal('');
  readonly show = signal<Record<AedAvailability, boolean>>({
    otwarte: true,
    zamkniete: true,
    nieznane: true,
    niesprawny: true,
  });
  readonly limit = signal(AED_PAGE_SIZE);
  readonly focus = signal<LatLngTuple | null>(null);

  mode: TimeMode = 'now';
  day = (new Date().getDay() + 6) % 7;
  hour = new Date().getHours();

  readonly counts = computed(() => {
    const result = { otwarte: 0, zamkniete: 0, nieznane: 0, niesprawny: 0 } as Record<AedAvailability, number>;
    this.points().forEach((p) => result[p.dostepnosc]++);
    return result;
  });

  readonly filtered = computed(() => {
    const q = this.query().trim().toLowerCase();
    const show = this.show();
    return this.points()
      .filter(
        (p) => show[p.dostepnosc] && (!q || `${p.nazwa_obiektu} ${p.adres} ${p.instytucja}`.toLowerCase().includes(q)),
      )
      .sort((a, b) => this.order.indexOf(a.dostepnosc) - this.order.indexOf(b.dostepnosc));
  });

  readonly visible = computed(() => this.filtered().slice(0, this.limit()));

  constructor(
    private readonly aed: AedService,
    private readonly router: Router,
    private readonly localize: LocalizeRouterService,
    readonly translate: TranslateService,
    @Inject(DOCUMENT) private readonly document: Document,
  ) {}

  ngOnInit(): void {
    this.load();
  }

  get hourLabel(): string {
    return String(this.hour).padStart(2, '0') + ':00';
  }

  batteryWidth(percent: number): number {
    return (BATTERY_INNER_WIDTH * Math.max(percent, BATTERY_MIN_PERCENT)) / 100;
  }

  load(): void {
    this.loading.set(true);
    this.aed
      .list(this.mode === 'chosen' ? this.chosenMoment() : undefined)
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({ next: (points) => this.points.set(points), error: () => this.error.set('Aed.ErrList') });
  }

  setMode(mode: TimeMode): void {
    this.mode = mode;
    this.load();
  }

  toggle(a: AedAvailability, on: boolean): void {
    this.show.update((s) => ({ ...s, [a]: on }));
  }

  showMore(): void {
    this.limit.update((n) => n + AED_PAGE_STEP);
  }

  open(p: AedBrief): void {
    this.router.navigate(this.localize.translateRoute([AED_ROUTE, p.id]) as unknown[]);
  }

  locate(p: AedBrief): void {
    this.focus.set([p.lat, p.lon]);
  }

  scrollTo(event: Event, id: string): void {
    event.preventDefault();
    this.document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  /** Najbliższy wybrany dzień tygodnia o wybranej godzinie, w formacie API: RRRR-MM-DDTGG:MM. */
  private chosenMoment(): string {
    const now = new Date();
    const date = new Date(now);
    date.setDate(now.getDate() + ((this.day - ((now.getDay() + 6) % 7) + 7) % 7));
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(this.hour)}:00`;
  }
}
