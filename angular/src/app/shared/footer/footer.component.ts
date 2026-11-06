import { Component, ChangeDetectionStrategy } from '@angular/core';
import { TranslocoDirective } from '@jsverse/transloco';

@Component({
  selector: 'shpp-footer',
  templateUrl: './footer.component.html',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.Eager,
  imports: [ TranslocoDirective ]
})
export class FooterComponent {

}
