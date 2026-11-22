import { ChangeDetectionStrategy, Component, ElementRef, HostListener, Input, ViewChild } from '@angular/core';
import { TranslatePipe } from '@ngx-translate/core';

import { AED_SINGLE_PATH, AED_WIZARD_PATH } from '@app/pages/aed/aed.constants';
import { AedService } from '@app/pages/aed/aed.service';

/** "Dodaj dane o AED" as a menu: one AED in a minute, or many from a file. */
@Component({
  selector: 'app-aed-add-menu',
  standalone: true,
  imports: [TranslatePipe],
  templateUrl: './aed-add-menu.component.html',
  styleUrls: ['./aed-add-menu.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AedAddMenuComponent {
  @Input() variant: 'banner' | 'hero' = 'hero';
  @ViewChild('menu', { static: true }) menu!: ElementRef<HTMLDetailsElement>;

  readonly singleUrl = this.aed.adminUrl(AED_SINGLE_PATH);
  readonly wizardUrl = this.aed.adminUrl(AED_WIZARD_PATH);

  constructor(
    private readonly aed: AedService,
    private readonly host: ElementRef<HTMLElement>,
  ) {}

  @HostListener('document:click', ['$event'])
  closeOutside(event: Event): void {
    if (!this.host.nativeElement.contains(event.target as Node)) {
      this.menu.nativeElement.open = false;
    }
  }

  @HostListener('keydown.escape')
  close(): void {
    const menu = this.menu.nativeElement;
    if (menu.open) {
      menu.open = false;
      menu.querySelector('summary')?.focus();
    }
  }
}
