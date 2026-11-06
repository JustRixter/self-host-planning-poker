import { Component, ChangeDetectionStrategy, Input } from '@angular/core';
import { NavigationBarComponent } from '../../navigation-bar/navigation-bar.component';

@Component({
  standalone: true,
  selector: 'shpp-container',
  templateUrl: './container.component.html',
  changeDetection: ChangeDetectionStrategy.Eager,
  imports: [ NavigationBarComponent ]
})
export class ContainerComponent {
  /** Whether the navigation bar shows the theme toggle on its own */
  @Input() themeToggle = true;
}
