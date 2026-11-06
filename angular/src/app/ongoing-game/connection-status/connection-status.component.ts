import { ChangeDetectionStrategy, Component, DestroyRef } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NgbTooltip } from '@ng-bootstrap/ng-bootstrap';
import { TranslocoDirective } from '@jsverse/transloco';
import { ConnectionState, CurrentGameService } from '../current-game.service';

/** A problem has to last this long to be shown: a connection that comes back right away does not deserve a flash */
const SHOW_AFTER_MS = 1_500;

/** A red icon that only appears when the connection to the server is lost, with no toasts */
@Component({
  standalone: true,
  selector: 'shpp-connection-status',
  templateUrl: './connection-status.component.html',
  styleUrl: './connection-status.component.scss',
  changeDetection: ChangeDetectionStrategy.Eager,
  imports: [TranslocoDirective, NgbTooltip]
})
export class ConnectionStatusComponent {
  /** What is displayed: nothing when everything is fine */
  problem: Exclude<ConnectionState, 'connected'> | null = null;

  private timer?: ReturnType<typeof setTimeout>;

  constructor(currentGameService: CurrentGameService, destroyRef: DestroyRef) {
    currentGameService.connection$
      .pipe(takeUntilDestroyed(destroyRef))
      .subscribe((state) => this.update(state));
    destroyRef.onDestroy(() => clearTimeout(this.timer));
  }

  reload(): void {
    window.location.reload();
  }

  private update(state: ConnectionState): void {
    if (state === 'connected') {
      clearTimeout(this.timer);
      this.timer = undefined;
      this.problem = null;
    } else if (state === 'failed') {
      clearTimeout(this.timer);
      this.timer = undefined;
      this.problem = 'failed';
    } else if (this.problem === null && this.timer === undefined) {
      this.timer = setTimeout(() => {
        this.timer = undefined;
        this.problem = 'reconnecting';
      }, SHOW_AFTER_MS);
    }
  }
}
