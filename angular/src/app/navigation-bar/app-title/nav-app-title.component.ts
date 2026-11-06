import { Component, ChangeDetectionStrategy } from '@angular/core';
import { TranslocoDirective } from '@jsverse/transloco';

@Component({
  selector: 'shpp-nav-app-title',
  templateUrl: './nav-app-title.component.html',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.Eager,
  imports: [ TranslocoDirective ]
})
export class NavAppTitleComponent {

}
