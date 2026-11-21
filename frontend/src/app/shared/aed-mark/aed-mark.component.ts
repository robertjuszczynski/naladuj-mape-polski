import { ChangeDetectionStrategy, Component } from '@angular/core';

import { AED_OUTLINE, AED_PULSE, AED_VIEWBOX } from '@app/pages/aed/aed-geometry';

/** Sygnet akcji: kontur Polski i puls. Kolory z --aed-mark-outline i --aed-mark-pulse. */
@Component({
  selector: 'app-aed-mark',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg [attr.viewBox]="viewBox" aria-hidden="true" focusable="false">
      <path class="outline" pathLength="100" [attr.d]="outline" />
      <path class="pulse" pathLength="100" [attr.d]="pulse" />
    </svg>
  `,
  styles: [
    `
      :host {
        display: block;
      }
      svg {
        display: block;
        width: 100%;
        height: auto;
        overflow: visible;
      }
      path {
        fill: none;
        stroke-width: 6.8;
        stroke-linecap: round;
        stroke-linejoin: round;
        stroke-dasharray: 100;
      }
      .outline {
        stroke: var(--aed-mark-outline, currentColor);
        animation: draw 0.7s linear both;
      }
      .pulse {
        stroke: var(--aed-mark-pulse, #d62839);
        animation: draw 0.35s cubic-bezier(0.5, 0.5, 0.15, 1) 0.7s both;
      }
      @keyframes draw {
        from {
          stroke-dashoffset: 100;
        }
      }
      @media (prefers-reduced-motion: reduce) {
        path {
          animation: none;
        }
      }
    `,
  ],
})
export class AedMarkComponent {
  readonly viewBox = AED_VIEWBOX;
  readonly outline = AED_OUTLINE;
  readonly pulse = AED_PULSE;
}
