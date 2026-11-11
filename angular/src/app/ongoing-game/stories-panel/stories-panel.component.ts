import { ChangeDetectionStrategy, Component, OnDestroy } from '@angular/core';
import { AsyncPipe } from '@angular/common';
import { TranslocoDirective, TranslocoService } from '@jsverse/transloco';
import { map, Observable } from 'rxjs';
import { CurrentGameService } from '../current-game.service';
import { CardValue, decksDict, displayCardValue } from '../../model/deck';
import { Story } from '../../model/events';
import { copyTable } from './clipboard';
import { parseStories } from './parse-stories';

interface StoryRow {
  id: number;
  name: string;
  ref: string | null;
  url: string | null;
  estimate: number;
  display: string | number;
  /** "Anna: 5, Oleh: 8", shown when hovering the estimate */
  votes: string;
}

interface StoriesView {
  backlog: Story[];
  stories: StoryRow[];
  /** Cards that can be chosen as the estimate of a story */
  cards: CardValue[];
  total: number;
  /** Adding up t-shirt sizes makes no sense */
  showPoints: boolean;
}

/**
 * Always visible list of the stories: the backlog of the stories to estimate (the first one is estimated at the
 * next reveal), then the estimated stories (one is added each time the cards are revealed)
 */
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
  newStories = '';

  private copyTimeout?: ReturnType<typeof setTimeout>;

  constructor(private currentGameService: CurrentGameService,
              private transloco: TranslocoService) {
    this.view$ = currentGameService.gameInfo$.pipe(
      map((info) => {
        const deck = info ? decksDict[info.deck] : undefined;
        const display = (card: number) => (deck && displayCardValue(deck, card)) ?? card;
        return {
          backlog: info?.backlog ?? [],
          stories: (info?.history ?? []).map((entry) => ({
            id: entry.id,
            name: entry.name,
            ref: entry.ref ?? null,
            url: entry.url ?? null,
            estimate: entry.estimate,
            display: display(entry.estimate),
            votes: (entry.votes ?? []).map((vote) => `${vote.player}: ${display(vote.card)}`).join(', ')
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

  /** position starts at 1 */
  move(id: number, position: number): void {
    this.currentGameService.moveStory(id, position);
  }

  requeue(id: number): void {
    this.currentGameService.requeueStory(id);
  }

  clearBacklog(): void {
    if (confirm(this.transloco.translate('stories.clearConfirm'))) {
      this.currentGameService.clearBacklog();
    }
  }

  addStories(): void {
    const stories = parseStories(this.newStories);
    if (stories.length > 0) {
      this.currentGameService.addToBacklog(stories);
    }
    this.newStories = '';
  }

  /** Enter adds the stories, Shift+Enter starts a new line (pasting several lines works too) */
  onAddKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      this.addStories();
    }
  }

  /** Copies the stories as a table that can be pasted in a spreadsheet, a wiki page or a document */
  async copyAll(stories: StoryRow[]): Promise<void> {
    const t = (key: string, params?: Record<string, unknown>) => this.transloco.translate(`stories.${key}`, params);
    const withRefs = stories.some((story) => story.ref);
    const header = withRefs
      ? [t('refHeader'), t('storyHeader'), t('estimateHeader')]
      : [t('storyHeader'), t('estimateHeader')];
    const rows = stories.map((story, index) => {
      const row = [story.name || t('unnamed', { number: index + 1 }), String(story.display)];
      return withRefs ? [story.ref ?? '', ...row] : row;
    });
    const copied = await copyTable(header, rows);
    this.copyState = copied ? 'copied' : 'failed';
    clearTimeout(this.copyTimeout);
    this.copyTimeout = setTimeout(() => this.copyState = 'idle', 2000);
  }

  ngOnDestroy(): void {
    clearTimeout(this.copyTimeout);
  }
}
