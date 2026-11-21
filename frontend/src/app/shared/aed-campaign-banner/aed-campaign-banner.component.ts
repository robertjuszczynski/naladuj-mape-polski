import { AsyncPipe, NgIf } from '@angular/common';
import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { LocalizeRouterPipe } from '@gilsdav/ngx-translate-router';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';

import { AED_ROUTE, AED_WIZARD_PATH } from '@app/pages/aed/aed.constants';
import { AedNumberPipe } from '@app/pages/aed/aed-number.pipe';
import { AedService } from '@app/pages/aed/aed.service';
import { AedMarkComponent } from '@app/shared/aed-mark/aed-mark.component';

@Component({
  selector: 'app-aed-campaign-banner',
  standalone: true,
  imports: [NgIf, AsyncPipe, RouterLink, LocalizeRouterPipe, TranslatePipe, AedMarkComponent, AedNumberPipe],
  templateUrl: './aed-campaign-banner.component.html',
  styleUrls: ['./aed-campaign-banner.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AedCampaignBannerComponent {
  readonly route = AED_ROUTE;
  readonly stats$ = this.aed.stats$;
  readonly wizardUrl = this.aed.adminUrl(AED_WIZARD_PATH);

  constructor(
    private readonly aed: AedService,
    readonly translate: TranslateService,
  ) {}
}
