import { ChangeDetectionStrategy, Component } from '@angular/core';
import { AsyncPipe } from '@angular/common';
import { TranslocoDirective } from '@jsverse/transloco';
import { map, Observable } from 'rxjs';
import { CurrentGameService } from '../current-game.service';
import { decksDict, displayCardValue } from '../../model/deck';

interface CurrentStoryView {
  name: string;
  ref: string | null;
  url: string | null;
  /** Shown once the cards are revealed */
  estimate: string | number | null;
  /** Other stories wait in the backlog: this one can be skipped */
  canSkip: boolean;
}

/** The story the team is estimating, above the table. Hidden when the backlog is empty. */
@Component({
  standalone: true,
  selector: 'shpp-current-story',
  templateUrl: './current-story.component.html',
  styleUrl: './current-story.component.scss',
  changeDetection: ChangeDetectionStrategy.Eager,
  imports: [TranslocoDirective, AsyncPipe]
})
export class CurrentStoryComponent {
  view$: Observable<CurrentStoryView | null>;

  constructor(private currentGameService: CurrentGameService) {
    this.view$ = currentGameService.gameInfo$.pipe(
      map((info) => {
        const current = info?.current;
        if (!info || !current) {
          return null;
        }
        const estimated = 'estimate' in current;
        const deck = decksDict[info.deck];
        return {
          name: current.name,
          ref: current.ref ?? null,
          url: current.url ?? null,
          estimate: estimated ? ((deck && displayCardValue(deck, current.estimate)) ?? current.estimate) : null,
          canSkip: !estimated && !info.revealed && (info.backlog?.length ?? 0) > 1
        };
      })
    );
  }

  skip(): void {
    this.currentGameService.skipStory();
  }
}
