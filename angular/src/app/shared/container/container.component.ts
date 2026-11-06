import { Component, ChangeDetectionStrategy } from '@angular/core';
import { NavigationBarComponent } from '../../navigation-bar/navigation-bar.component';

@Component({
  standalone: true,
  selector: 'shpp-container',
  templateUrl: './container.component.html',
  changeDetection: ChangeDetectionStrategy.Eager,
  imports: [ NavigationBarComponent ]
})
export class ContainerComponent {

}
