import { Component, ChangeDetectionStrategy } from '@angular/core';
import { TranslocoDirective } from '@jsverse/transloco';
import { ThemeService } from './theme.service';

@Component({
  standalone: true,
  selector: 'shpp-theme-toggle',
  imports: [TranslocoDirective],
  changeDetection: ChangeDetectionStrategy.Eager,
  template: `
    <button *transloco="let t; read 'theme'" type="button" class="btn btn-outline-secondary btn-sm"
            [attr.aria-label]="t('toggle', { mode: t(theme.preference) })"
            [title]="t('toggle', { mode: t(theme.preference) })"
            (click)="theme.cycle()">
      <svg class="bi" width="1em" height="1em" fill="currentColor" aria-hidden="true">
        <use [attr.xlink:href]="'assets/bootstrap-icons.svg#' + icon()"/>
      </svg>
    </button>
  `
})
export class ThemeToggleComponent {
  constructor(protected theme: ThemeService) {}

  icon(): string {
    return { auto: 'circle-half', light: 'sun-fill', dark: 'moon-stars-fill' }[this.theme.preference];
  }
}
