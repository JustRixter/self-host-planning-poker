import { Component } from '@angular/core';
import { TranslocoDirective } from '@jsverse/transloco';
import { ThemeToggleComponent } from '../shared/theme/theme-toggle.component';
import { BaseHrefPipe } from "../shared/base-href.pipe";

@Component({
  standalone: true,
  selector: 'shpp-navigation-bar',
  templateUrl: './navigation-bar.component.html',
  imports: [TranslocoDirective, BaseHrefPipe, ThemeToggleComponent],
  styleUrls: ['./navigation-bar.component.scss']
})
export class NavigationBarComponent {

}
