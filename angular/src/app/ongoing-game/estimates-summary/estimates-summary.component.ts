import { Component } from '@angular/core';
import { AsyncPipe, NgFor, NgIf } from '@angular/common';
import { TranslocoDirective } from '@jsverse/transloco';
import { map, Observable } from 'rxjs';
import { CurrentGameService } from '../current-game.service';
import { decksDict, displayCardValue } from '../../model/deck';

interface EstimateRow {
  display: string | number;
  stories: number;
}

interface EstimatesView {
  rows: EstimateRow[];
  total: number;
}

@Component({
  standalone: true,
  selector: 'shpp-estimates-summary',
  templateUrl: './estimates-summary.component.html',
  imports: [TranslocoDirective, AsyncPipe, NgFor, NgIf]
})
export class EstimatesSummaryComponent {
  view$: Observable<EstimatesView>;

  constructor(currentGameService: CurrentGameService) {
    this.view$ = currentGameService.gameInfo$.pipe(
      map((info) => {
        const deck = info ? decksDict[info.deck] : undefined;
        const rows = Object.entries(info?.estimates ?? {})
          .map(([value, stories]) => ({ value: Number(value), stories }))
          .sort((a, b) => a.value - b.value)
          .map(({ value, stories }) => ({
            display: (deck && displayCardValue(deck, value)) ?? value,
            stories
          }));
        return { rows, total: rows.reduce((sum, row) => sum + row.stories, 0) };
      })
    );
  }
}
