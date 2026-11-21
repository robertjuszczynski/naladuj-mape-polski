import { isPlatformBrowser } from '@angular/common';
import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  Inject,
  Input,
  NgZone,
  OnChanges,
  OnDestroy,
  Output,
  PLATFORM_ID,
  SimpleChanges,
  ViewChild,
} from '@angular/core';
import { TranslateService } from '@ngx-translate/core';
import type * as Leaflet from 'leaflet';

import { AedAvailability, AedBrief } from './aed.models';

declare const require: (name: string) => typeof Leaflet;

const POLAND_CENTER: Leaflet.LatLngTuple = [52.1, 19.4];
const POLAND_ZOOM = 6;
const CLUSTER_SPAN: Leaflet.LatLngTuple = [0.3, 0.45];
const COLOR_TOKENS: Record<AedAvailability, string> = {
  otwarte: '--aed-fg',
  zamkniete: '--aed-closed',
  nieznane: '--aed-unknown',
  niesprawny: '--aed-accent',
};

@Component({
  selector: 'app-aed-map',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div #map class="aed-map" role="region" [attr.aria-label]="label"></div>`,
  styles: [
    `
      :host {
        display: block;
      }
      .aed-map {
        width: 100%;
        height: 100%;
        min-height: 360px;
      }
    `,
  ],
})
export class AedMapComponent implements AfterViewInit, OnChanges, OnDestroy {
  @Input() points: AedBrief[] = [];
  @Input() center: Leaflet.LatLngTuple | null = null;
  @Input() zoom = 16;
  @Input() label = '';
  @Output() selected = new EventEmitter<AedBrief>();
  @ViewChild('map', { static: true }) mapEl!: ElementRef<HTMLDivElement>;

  private L?: typeof Leaflet;
  private map?: Leaflet.Map;
  private layer?: Leaflet.LayerGroup;
  private fitted = false;

  constructor(
    @Inject(PLATFORM_ID) private readonly platformId: object,
    private readonly zone: NgZone,
    private readonly host: ElementRef<HTMLElement>,
    private readonly translate: TranslateService,
  ) {}

  ngAfterViewInit(): void {
    if (!isPlatformBrowser(this.platformId)) {
      return;
    }
    this.zone.runOutsideAngular(() => {
      this.L = require('leaflet');
      this.map = this.L.map(this.mapEl.nativeElement, { preferCanvas: true }).setView(
        this.center ?? POLAND_CENTER,
        this.center ? this.zoom : POLAND_ZOOM,
      );
      this.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 19,
      }).addTo(this.map);
      this.layer = this.L.layerGroup().addTo(this.map);
      this.render();
      requestAnimationFrame(() => this.map?.invalidateSize());
    });
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['points']) {
      this.zone.runOutsideAngular(() => this.render());
    }
    if (changes['center'] && this.center && this.map && !this.sameCenter(changes['center'].previousValue)) {
      this.zone.runOutsideAngular(() =>
        this.map?.flyTo(this.center as Leaflet.LatLngTuple, this.zoom, { duration: 0.5 }),
      );
    }
  }

  ngOnDestroy(): void {
    this.map?.remove();
  }

  private render(): void {
    if (!this.L || !this.layer || !this.map) {
      return;
    }
    const style = getComputedStyle(this.host.nativeElement);
    const color = (a: AedAvailability) => style.getPropertyValue(COLOR_TOKENS[a]).trim();
    const ring = style.getPropertyValue('--aed-bg').trim() || '#fff';
    this.layer.clearLayers();
    const coords: Leaflet.LatLngTuple[] = [];
    for (const p of this.points) {
      if (p.lat == null || p.lon == null) {
        continue;
      }
      coords.push([p.lat, p.lon]);
      const open = p.dostepnosc === 'otwarte';
      this.L.circleMarker([p.lat, p.lon], {
        radius: open ? 7 : 5,
        color: ring,
        weight: 1.5,
        fillColor: color(p.dostepnosc),
        fillOpacity: 0.95,
      })
        .bindTooltip(`${p.nazwa_obiektu} – ${this.translate.instant('Aed.Avail.' + p.dostepnosc)}`)
        .on('click', () => this.zone.run(() => this.selected.emit(p)))
        .addTo(this.layer);
    }
    if (!this.fitted && !this.center && coords.length > 1) {
      this.map.fitBounds(this.L.latLngBounds(this.densestCluster(coords)), { padding: [24, 24], maxZoom: 13 });
      this.fitted = true;
    }
  }

  private sameCenter(previous: Leaflet.LatLngTuple | null): boolean {
    return !!previous && !!this.center && previous[0] === this.center[0] && previous[1] === this.center[1];
  }

  /** Pierwszy widok: skupisko wokół mediany punktów, jeśli obejmuje większość danych. */
  private densestCluster(coords: Leaflet.LatLngTuple[]): Leaflet.LatLngTuple[] {
    const median = (values: number[]) => [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
    const lat = median(coords.map((c) => c[0]));
    const lon = median(coords.map((c) => c[1]));
    const near = coords.filter((c) => Math.abs(c[0] - lat) < CLUSTER_SPAN[0] && Math.abs(c[1] - lon) < CLUSTER_SPAN[1]);
    return near.length >= coords.length / 2 ? near : coords;
  }
}
