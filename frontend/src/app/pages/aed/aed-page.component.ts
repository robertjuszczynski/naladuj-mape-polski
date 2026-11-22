import { AsyncPipe, DOCUMENT, NgFor, NgIf } from '@angular/common';
import { ChangeDetectionStrategy, Component, Inject, OnInit, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { LocalizeRouterPipe, LocalizeRouterService } from '@gilsdav/ngx-translate-router';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import type { LatLngTuple } from 'leaflet';
import { finalize } from 'rxjs';

import { AedAddMenuComponent } from '@app/shared/aed-add-menu/aed-add-menu.component';
import { AedMarkComponent } from '@app/shared/aed-mark/aed-mark.component';

import {
  AED_AVAILABILITY_ORDER,
  AED_PAGE_SIZE,
  AED_PAGE_STEP,
  AED_ROUTE,
  AED_SCOPE_PATH,
  AED_TEMPLATE_PATH,
  AED_SINGLE_PATH,
  AED_WIZARD_PATH,
} from './aed.constants';
import { AedAvailability, AedBrief, AedIncidentPoint, AedNearest } from './aed.models';
import { AedService } from './aed.service';
import { readableHours } from './aed-hours';
import { AedMapComponent } from './aed-map.component';
import { AedNumberPipe } from './aed-number.pipe';

type TimeMode = 'now' | 'chosen';
type IncidentQuery = { address: string } | { lat: number; lon: number };

const FAR_WALK_MIN = 5;
const NOT_FOUND = 404;
const GEO_OPTIONS: PositionOptions = { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 };

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
    AedAddMenuComponent,
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
  readonly singleUrl = this.aed.adminUrl(AED_SINGLE_PATH);
  readonly templateUrl = this.aed.adminUrl(AED_TEMPLATE_PATH);
  readonly scopeUrl = this.aed.adminUrl(AED_SCOPE_PATH);

  readonly points = signal<AedBrief[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly query = signal('');
  readonly show = signal<Record<AedAvailability, boolean>>({
    open: true,
    closed: true,
    unknown: true,
    faulty: true,
  });
  readonly limit = signal(AED_PAGE_SIZE);
  readonly focus = signal<LatLngTuple | null>(null);
  readonly incidentText = signal('');
  readonly nearest = signal<AedNearest | null>(null);
  readonly nearestLoading = signal(false);
  readonly nearestError = signal('');
  readonly copied = signal(-1);
  readonly locating = signal(false);
  readonly farWalkMin = FAR_WALK_MIN;
  private incident: IncidentQuery | null = null;
  private incidentLabel: Pick<AedIncidentPoint, 'label' | 'exact'> | null = null;

  readonly incidentPoint = computed<LatLngTuple | null>(() => {
    const point = this.nearest()?.meta.point;
    return point ? [point.lat, point.lon] : null;
  });

  mode: TimeMode = 'now';
  day = (new Date().getDay() + 6) % 7;
  hour = new Date().getHours();

  readonly counts = computed(() => {
    const result = { open: 0, closed: 0, unknown: 0, faulty: 0 } as Record<AedAvailability, number>;
    this.points().forEach((p) => result[p.availability]++);
    return result;
  });

  readonly filtered = computed(() => {
    const q = this.query().trim().toLowerCase();
    const show = this.show();
    return this.points()
      .filter(
        (p) => show[p.availability] && (!q || `${p.name} ${p.address} ${p.institution}`.toLowerCase().includes(q)),
      )
      .sort((a, b) => this.order.indexOf(a.availability) - this.order.indexOf(b.availability));
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
    this.locateIfAllowed();
  }

  get canLocate(): boolean {
    return !!this.document.defaultView?.navigator.geolocation;
  }

  useMyLocation(): void {
    const geolocation = this.document.defaultView?.navigator.geolocation;
    if (!geolocation) {
      return;
    }
    this.locating.set(true);
    this.nearestError.set('');
    geolocation.getCurrentPosition(
      ({ coords }) => {
        this.locating.set(false);
        this.incidentText.set('');
        this.incident = { lat: coords.latitude, lon: coords.longitude };
        this.incidentLabel = { label: this.translate.instant('Aed.Nearest.MyLocation'), exact: true };
        this.findNearest();
      },
      () => {
        this.locating.set(false);
        this.nearestError.set('Aed.Nearest.GeoDenied');
      },
      GEO_OPTIONS,
    );
  }

  /** Searches from the visitor's position on load only when they already allowed it, so the page never opens with a prompt. */
  private locateIfAllowed(): void {
    const permissions = this.document.defaultView?.navigator.permissions;
    permissions
      ?.query({ name: 'geolocation' })
      .then((status) => status.state === 'granted' && this.useMyLocation())
      .catch(() => undefined);
  }

  get hourLabel(): string {
    return String(this.hour).padStart(2, '0') + ':00';
  }

  get timeLabel(): string {
    return this.mode === 'now'
      ? this.translate.instant('Aed.NowLower')
      : `${this.translate.instant('Aed.Days.' + this.day)}, ${this.hourLabel}`;
  }

  load(): void {
    this.loading.set(true);
    if (this.incident) {
      this.findNearest();
    }
    this.aed
      .list(this.momentParam())
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

  findAddress(): void {
    const address = this.incidentText().trim();
    if (address) {
      this.incident = { address };
      this.incidentLabel = null;
      this.findNearest();
    }
  }

  pick([lat, lon]: LatLngTuple): void {
    this.incident = { lat, lon };
    this.incidentLabel = null;
    this.findNearest();
  }

  clearNearest(): void {
    this.incident = null;
    this.incidentLabel = null;
    this.nearest.set(null);
    this.nearestError.set('');
  }

  copyPhrase(index: number, phrase: string): void {
    this.document.defaultView?.navigator.clipboard?.writeText(phrase).then(() => this.copied.set(index));
  }

  /** "380 m" or "1,3 km" in the page language. */
  distance(meters: number): string {
    if (meters < 1000) {
      return `${meters} m`;
    }
    const km = new Intl.NumberFormat(this.translate.currentLang === 'en' ? 'en-GB' : 'pl-PL', {
      maximumFractionDigits: 1,
    }).format(meters / 1000);
    return `${km} km`;
  }

  hours(spec: string): string {
    return readableHours(spec, this.translate.currentLang);
  }

  /** "środa 07:00" for an ISO moment from the API. */
  opensLabel(iso: string): string {
    const [date, time] = iso.split('T');
    const [y, m, d] = date.split('-').map(Number);
    const weekday = (new Date(y, m - 1, d).getDay() + 6) % 7;
    return `${this.translate.instant('Aed.Days.' + weekday)} ${time.slice(0, 5)}`;
  }

  private findNearest(): void {
    if (!this.incident) {
      return;
    }
    this.nearestLoading.set(true);
    this.nearestError.set('');
    this.copied.set(-1);
    this.aed
      .nearest(this.incident, this.momentParam())
      .pipe(finalize(() => this.nearestLoading.set(false)))
      .subscribe({
        next: (result) => {
          if (!this.incident) {
            return;
          }
          const point = result.meta.point;
          if ('address' in this.incident) {
            this.incidentLabel = { label: point.label, exact: point.exact };
          }
          this.incident = { lat: point.lat, lon: point.lon };
          this.nearest.set({ ...result, meta: { ...result.meta, point: { ...point, ...this.incidentLabel } } });
        },
        error: (err) => {
          this.nearest.set(null);
          this.nearestError.set(err?.status === NOT_FOUND ? 'Aed.Nearest.NotFound' : 'Aed.Nearest.Error');
        },
      });
  }

  private momentParam(): string | undefined {
    return this.mode === 'chosen' ? this.chosenMoment() : undefined;
  }

  scrollTo(event: Event, id: string): void {
    event.preventDefault();
    this.document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  /** The next chosen weekday at the chosen hour, in the API format YYYY-MM-DDTHH:MM. */
  private chosenMoment(): string {
    const now = new Date();
    const date = new Date(now);
    date.setDate(now.getDate() + ((this.day - ((now.getDay() + 6) % 7) + 7) % 7));
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(this.hour)}:00`;
  }
}
