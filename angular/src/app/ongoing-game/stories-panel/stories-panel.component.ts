import { ChangeDetectionStrategy, Component, OnDestroy } from '@angular/core';
import { AsyncPipe } from '@angular/common';
import { TranslocoDirective, TranslocoService } from '@jsverse/transloco';
import { map, Observable } from 'rxjs';
import { CurrentGameService } from '../current-game.service';
import { CardValue, decksDict, displayCardValue } from '../../model/deck';
import { copyTable } from './clipboard';

interface StoryRow {
  id: number;
  name: string;
  estimate: number;
  display: string | number;
}

interface StoriesView {
  stories: StoryRow[];
  /** Cards that can be chosen as the estimate of a story */
  cards: CardValue[];
  total: number;
  /** Adding up t-shirt sizes makes no sense */
  showPoints: boolean;
}

/** Always visible list of the estimated stories: one is added each time the cards are revealed */
@Component({
  standalone: true,
  selector: 'shpp-stories-panel',
  templateUrl: './stories-panel.component.html',
  changeDetection: ChangeDetectionStrategy.Eager,
  styleUrl: './stories-panel.component.scss',
  imports: [TranslocoDirective, AsyncPipe]
})
export class StoriesPanelComponent implements OnDestroy {
  view$: Observable<StoriesView>;
  copyState: 'idle' | 'copied' | 'failed' = 'idle';

  private copyTimeout?: ReturnType<typeof setTimeout>;

  constructor(private currentGameService: CurrentGameService,
              private transloco: TranslocoService) {
    this.view$ = currentGameService.gameInfo$.pipe(
      map((info) => {
        const deck = info ? decksDict[info.deck] : undefined;
        return {
          stories: (info?.history ?? []).map((entry) => ({
            id: entry.id,
            name: entry.name,
            estimate: entry.estimate,
            display: (deck && displayCardValue(deck, entry.estimate)) ?? entry.estimate
          })),
          cards: deck?.values ?? [],
          total: info?.total ?? 0,
          showPoints: !!deck && !deck.textValues
        };
      })
    );
  }

  rename(id: number, name: string): void {
    this.currentGameService.updateStory(id, { name: name });
  }

  setEstimate(id: number, estimate: string): void {
    this.currentGameService.updateStory(id, { estimate: Number(estimate) });
  }

  remove(id: number): void {
    this.currentGameService.deleteStory(id);
  }

  /** Copies the stories as a table that can be pasted in a spreadsheet, a wiki page or a document */
  async copyAll(stories: StoryRow[]): Promise<void> {
    const t = (key: string, params?: Record<string, unknown>) => this.transloco.translate(`stories.${key}`, params);
    const rows = stories.map((story, index) =>
      [story.name || t('unnamed', { number: index + 1 }), String(story.display)]);
    const copied = await copyTable([t('storyHeader'), t('estimateHeader')], rows);
    this.copyState = copied ? 'copied' : 'failed';
    clearTimeout(this.copyTimeout);
    this.copyTimeout = setTimeout(() => this.copyState = 'idle', 2000);
  }

  ngOnDestroy(): void {
    clearTimeout(this.copyTimeout);
  }
}
