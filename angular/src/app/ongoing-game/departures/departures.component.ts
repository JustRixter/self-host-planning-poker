import { ChangeDetectionStrategy, Component, DestroyRef } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { TranslocoDirective, TranslocoService } from '@jsverse/transloco';
import { CurrentGameService } from '../current-game.service';

/** A departure is only announced if the person has not come back by then (a reload or a flaky connection) */
const GRACE_MS = 5_000;
/** How long a departure is mentioned (counted from the moment it is announced) */
const DISPLAY_MS = 30_000;
/** The names beyond this number are summed up ("and 3 more") */
const MAX_NAMES = 2;

/**
 * Says, in a discreet line on the table, who has just left the game: their cards disappear, which could go unnoticed.
 *
 * Meant not to be a nuisance when somebody keeps joining and leaving: nothing is said about somebody who comes back
 * within a few seconds, everybody is merged in one line (no stack of notices), and the line fades by itself.
 */
@Component({
  standalone: true,
  selector: 'shpp-departures',
  templateUrl: './departures.component.html',
  styleUrl: './departures.component.scss',
  changeDetection: ChangeDetectionStrategy.Eager,
  imports: [TranslocoDirective]
})
export class DeparturesComponent {
  /** The names to display, and how many other people left too */
  shown: string[] = [];
  extra = 0;

  // The people who left less than GRACE_MS ago, who are not announced yet
  private pending = new Map<string, ReturnType<typeof setTimeout>>();
  // The people who are announced. The insertion order is the order of the departures
  private gone = new Map<string, ReturnType<typeof setTimeout>>();

  constructor(currentGameService: CurrentGameService,
              private transloco: TranslocoService,
              destroyRef: DestroyRef) {
    currentGameService.departures$
      .pipe(takeUntilDestroyed(destroyRef))
      .subscribe((name) => this.left(name));
    currentGameService.state$
      .pipe(takeUntilDestroyed(destroyRef))
      .subscribe((state) => this.back(new Set(Object.values(state).map((player) => player.name))));
    destroyRef.onDestroy(() => {
      this.pending.forEach((timer) => clearTimeout(timer));
      this.gone.forEach((timer) => clearTimeout(timer));
    });
  }

  /** "Bob and Priya", "Bob, Priya and 3 more" (the list separators depend on the language) */
  format(names: string[], more?: string): string {
    const items = more ? [...names, more] : names;
    try {
      return new Intl.ListFormat(this.transloco.getActiveLang(), { style: 'long', type: 'conjunction' }).format(items);
    } catch {
      return items.join(', ');
    }
  }

  private left(name: string): void {
    this.forget(name);
    this.pending.set(name, setTimeout(() => {
      this.pending.delete(name);
      this.announce(name);
    }, GRACE_MS));
  }

  private announce(name: string): void {
    this.gone.set(name, setTimeout(() => {
      this.gone.delete(name);
      this.refresh();
    }, DISPLAY_MS));
    this.refresh();
  }

  private back(present: Set<string>): void {
    const announced = [...this.gone.keys()].some((name) => present.has(name));
    [...this.pending.keys(), ...this.gone.keys()]
      .filter((name) => present.has(name))
      .forEach((name) => this.forget(name));
    if (announced) {
      this.refresh();
    }
  }

  private forget(name: string): void {
    clearTimeout(this.pending.get(name));
    clearTimeout(this.gone.get(name));
    this.pending.delete(name);
    this.gone.delete(name);
  }

  private refresh(): void {
    const names = [...this.gone.keys()];
    this.shown = names.slice(0, MAX_NAMES);
    this.extra = Math.max(0, names.length - MAX_NAMES);
  }
}
