import { Component, ChangeDetectionStrategy } from '@angular/core';
import { AsyncPipe } from '@angular/common';
import { TranslocoDirective } from '@jsverse/transloco';
import { map, Observable } from 'rxjs';
import { CurrentGameService } from '../current-game.service';
import { decksDict, displayCardValue } from '../../model/deck';

interface EstimateRow {
  display: string | number;
  stories: number;
}

interface HistoryRow {
  name: string;
  display: string | number;
}

interface EstimatesView {
  rows: EstimateRow[];
  history: HistoryRow[];
  count: number;
  total: number;
  /** Adding up t-shirt sizes makes no sense */
  showPoints: boolean;
}

@Component({
  standalone: true,
  selector: 'shpp-estimates-summary',
  templateUrl: './estimates-summary.component.html',
  changeDetection: ChangeDetectionStrategy.Eager,
  imports: [TranslocoDirective, AsyncPipe]
})
export class EstimatesSummaryComponent {
  view$: Observable<EstimatesView>;

  constructor(currentGameService: CurrentGameService) {
    this.view$ = currentGameService.gameInfo$.pipe(
      map((info) => {
        const deck = info ? decksDict[info.deck] : undefined;
        const display = (value: number) => (deck && displayCardValue(deck, value)) ?? value;
        const rows = Object.entries(info?.estimates ?? {})
          .map(([value, stories]) => ({ value: Number(value), stories }))
          .sort((a, b) => a.value - b.value)
          .map(({ value, stories }) => ({ display: display(value), stories }));
        const history = (info?.history ?? []).map((entry) => ({
          name: entry.name,
          display: display(entry.estimate)
        }));
        return {
          rows,
          history,
          count: history.length,
          total: info?.total ?? 0,
          showPoints: !!deck && !deck.textValues
        };
      })
    );
  }
}
