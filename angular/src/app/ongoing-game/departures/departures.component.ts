import { ChangeDetectionStrategy, Component, DestroyRef } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { TranslocoDirective } from '@jsverse/transloco';
import { CurrentGameService } from '../current-game.service';

interface Departure {
  id: number;
  name: string;
}

/** How long a departure stays on screen, and how many are shown at once */
const DISPLAY_MS = 60_000;
const MAX_SHOWN = 3;

/** Tells who has just left the game: their cards disappear from the table, which could go unnoticed */
@Component({
  standalone: true,
  selector: 'shpp-departures',
  templateUrl: './departures.component.html',
  styleUrl: './departures.component.scss',
  changeDetection: ChangeDetectionStrategy.Eager,
  imports: [TranslocoDirective]
})
export class DeparturesComponent {
  departures: Departure[] = [];

  private nextId = 0;
  private timers = new Set<ReturnType<typeof setTimeout>>();

  constructor(currentGameService: CurrentGameService, destroyRef: DestroyRef) {
    currentGameService.departures$
      .pipe(takeUntilDestroyed(destroyRef))
      .subscribe((name) => this.add(name));
    destroyRef.onDestroy(() => this.timers.forEach((timer) => clearTimeout(timer)));
  }

  dismiss(id: number): void {
    this.departures = this.departures.filter((departure) => departure.id !== id);
  }

  private add(name: string): void {
    const departure = { id: this.nextId++, name: name };
    this.departures = [...this.departures, departure].slice(-MAX_SHOWN);
    const timer = setTimeout(() => {
      this.timers.delete(timer);
      this.dismiss(departure.id);
    }, DISPLAY_MS);
    this.timers.add(timer);
  }
}
