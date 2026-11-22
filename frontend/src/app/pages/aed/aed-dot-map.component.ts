import { HttpClient } from '@angular/common/http';
import { isPlatformBrowser, NgFor, NgIf } from '@angular/common';
import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  Inject,
  PLATFORM_ID,
  computed,
  input,
  model,
  signal,
} from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { TranslatePipe } from '@ngx-translate/core';
import { catchError, of } from 'rxjs';

import { AedBrief, AedProvinceCoverage } from './aed.models';

interface DotGrid {
  grid: { lon0: number; lat1: number; step: number; kx: number; cols: number; rows: number };
  names: Record<string, string>;
  dots: [number, number, string][];
}

interface Dot {
  x: number;
  y: number;
  code: string;
  aeds: number;
  delay: number;
}

const DOTS_URL = '/assets/aed/poland-dots.json';
const POP_STEP_MS = 18;
const POP_MAX_MS = 1600;

/** Poland as a grid of dots (one dot is about 12 x 12 km); a dot turns red when there is an AED in the register there. */
@Component({
  selector: 'app-aed-dot-map',
  standalone: true,
  imports: [NgFor, NgIf, TranslatePipe],
  template: `
    <figure class="dotmap" [class.is-live]="live()" (mouseleave)="leave()">
      <svg
        *ngIf="data() as d"
        [attr.viewBox]="'-1 -1 ' + (d.grid.cols + 1) + ' ' + (d.grid.rows + 1)"
        role="img"
        [attr.aria-label]="'Aed.DotMap.Label' | translate: { n: litCount() }"
        (mousemove)="hover($event)">
        <circle
          *ngFor="let dot of dots(); trackBy: trackDot"
          [attr.cx]="dot.x"
          [attr.cy]="dot.y"
          [attr.r]="dot.aeds ? 0.42 : 0.3"
          [attr.data-code]="dot.code"
          [class.on]="dot.aeds > 0"
          [class.dim]="highlight() && highlight() !== dot.code"
          [class.hl]="highlight() === dot.code"
          [style.--d]="dot.delay + 'ms'"></circle>
      </svg>
      <div class="dotmap__tip" *ngIf="tip() as t" [style.left.px]="t.x" [style.top.px]="t.y" aria-hidden="true">
        <strong>{{ t.name }}</strong>
        <span>{{ 'Aed.DotMap.Aeds' | translate: { n: t.aeds } }}</span>
        <span *ngIf="t.province"
          >{{ t.province.municipalities }}/{{ t.province.total }} {{ 'Aed.Municipalities' | translate }} ·
          {{ t.province.percent }}%</span
        >
      </div>
      <figcaption class="dotmap__legend">
        <span><i class="on"></i>{{ 'Aed.DotMap.On' | translate }}</span>
        <span><i></i>{{ 'Aed.DotMap.Off' | translate }}</span>
      </figcaption>
    </figure>
  `,
  styleUrls: ['./aed-dot-map.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AedDotMapComponent implements AfterViewInit {
  readonly points = input<AedBrief[]>([]);
  readonly provinces = input<AedProvinceCoverage[]>([]);
  readonly highlight = model<string | null>(null);

  readonly live = signal(false);
  readonly tip = signal<{ x: number; y: number; name: string; aeds: number; province?: AedProvinceCoverage } | null>(
    null,
  );
  readonly data = toSignal(this.http.get<DotGrid>(DOTS_URL).pipe(catchError(() => of(null))), { initialValue: null });

  /** AED count per grid cell; a point on the coast or border goes to the nearest dot of the grid. */
  private readonly cells = computed(() => {
    const d = this.data();
    const counts = new Map<string, number>();
    if (!d) {
      return counts;
    }
    const known = new Set(d.dots.map(([c, r]) => c + ',' + r));
    const { lon0, lat1, step, kx } = d.grid;
    for (const p of this.points()) {
      const col = Math.round(((p.lon - lon0) * kx) / step);
      const row = Math.round((lat1 - p.lat) / step);
      const key = [
        [0, 0],
        [1, 0],
        [-1, 0],
        [0, 1],
        [0, -1],
      ]
        .map(([dc, dr]) => col + dc + ',' + (row + dr))
        .find((k) => known.has(k));
      if (key) {
        counts.set(key, (counts.get(key) ?? 0) + 1);
      }
    }
    return counts;
  });

  readonly dots = computed<Dot[]>(() => {
    const d = this.data();
    if (!d) {
      return [];
    }
    const cells = this.cells();
    let lit = 0;
    return d.dots.map(([x, y, code]) => {
      const aeds = cells.get(x + ',' + y) ?? 0;
      const delay = aeds ? Math.min(lit++ * POP_STEP_MS, POP_MAX_MS) : 0;
      return { x, y, code, aeds, delay };
    });
  });

  readonly litCount = computed(() => this.dots().filter((d) => d.aeds > 0).length);

  private readonly aedsByProvince = computed(() => {
    const out = new Map<string, number>();
    this.dots().forEach((d) => out.set(d.code, (out.get(d.code) ?? 0) + d.aeds));
    return out;
  });

  constructor(
    private readonly http: HttpClient,
    private readonly host: ElementRef<HTMLElement>,
    private readonly destroyRef: DestroyRef,
    @Inject(PLATFORM_ID) private readonly platformId: object,
  ) {}

  ngAfterViewInit(): void {
    if (!isPlatformBrowser(this.platformId) || typeof IntersectionObserver === 'undefined') {
      this.live.set(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          this.live.set(true);
          observer.disconnect();
        }
      },
      { threshold: 0.25 },
    );
    observer.observe(this.host.nativeElement);
    this.destroyRef.onDestroy(() => observer.disconnect());
  }

  trackDot(_: number, dot: Dot): string {
    return dot.x + ',' + dot.y;
  }

  hover(event: MouseEvent): void {
    const target = event.target as Element;
    const code = target.getAttribute?.('data-code');
    const d = this.data();
    if (!code || !d) {
      return;
    }
    const box = this.host.nativeElement.getBoundingClientRect();
    this.highlight.set(code);
    this.tip.set({
      x: event.clientX - box.left,
      y: event.clientY - box.top,
      name: d.names[code] ?? code,
      aeds: this.aedsByProvince().get(code) ?? 0,
      province: this.provinces().find((p) => p.code === code),
    });
  }

  leave(): void {
    this.tip.set(null);
    this.highlight.set(null);
  }
}
