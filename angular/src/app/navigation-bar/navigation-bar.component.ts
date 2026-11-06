import { Component, ChangeDetectionStrategy, Input } from '@angular/core';
import { TranslocoDirective } from '@jsverse/transloco';
import { ThemeToggleComponent } from '../shared/theme/theme-toggle.component';
import { BaseHrefPipe } from "../shared/base-href.pipe";

@Component({
  standalone: true,
  selector: 'shpp-navigation-bar',
  templateUrl: './navigation-bar.component.html',
  imports: [TranslocoDirective, BaseHrefPipe, ThemeToggleComponent],
  changeDetection: ChangeDetectionStrategy.Eager,
  styleUrls: ['./navigation-bar.component.scss']
})
export class NavigationBarComponent {
  /** Pages that show the theme toggle themselves (in their own controls) turn this off */
  @Input() themeToggle = true;

}
