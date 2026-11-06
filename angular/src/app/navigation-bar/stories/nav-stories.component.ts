import { ChangeDetectionStrategy, Component, TemplateRef } from '@angular/core';
import { AsyncPipe } from '@angular/common';
import { NgbOffcanvas, NgbTooltip } from '@ng-bootstrap/ng-bootstrap';
import { TranslocoDirective, TranslocoService } from '@jsverse/transloco';
import { map, Observable } from 'rxjs';
import { CurrentGameService } from '../../ongoing-game/current-game.service';
import { CardValue, decksDict, displayCardValue } from '../../model/deck';
import { copyTable } from './clipboard';

interface StoryRow {
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

/** Navbar button showing how many stories were estimated, opening the list of their estimates */
@Component({
  standalone: true,
  selector: 'shpp-nav-stories',
  templateUrl: './nav-stories.component.html',
  changeDetection: ChangeDetectionStrategy.Eager,
  imports: [TranslocoDirective, AsyncPipe, NgbTooltip]
})
export class NavStoriesComponent {
  view$: Observable<StoriesView>;
  copyState: 'idle' | 'copied' | 'failed' = 'idle';

  private copyTimeout?: ReturnType<typeof setTimeout>;

  constructor(private currentGameService: CurrentGameService,
              private offcanvasService: NgbOffcanvas,
              private transloco: TranslocoService) {
    this.view$ = currentGameService.gameInfo$.pipe(
      map((info) => {
        const deck = info ? decksDict[info.deck] : undefined;
        return {
          stories: (info?.history ?? []).map((entry) => ({
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

  open(content: TemplateRef<unknown>): void {
    this.offcanvasService.open(content, { ariaLabelledBy: 'stories-title', position: 'end' });
  }

  rename(index: number, name: string): void {
    this.currentGameService.updateStory(index, { name: name });
  }

  setEstimate(index: number, estimate: string): void {
    this.currentGameService.updateStory(index, { estimate: Number(estimate) });
  }

  /** Copies the stories as a table that can be pasted in a spreadsheet, a wiki page or a document */
  async copyAll(stories: StoryRow[]): Promise<void> {
    const t = (key: string) => this.transloco.translate(`stories.${key}`);
    const rows = stories.map((story) => [story.name || t('unnamed'), String(story.display)]);
    const copied = await copyTable([t('storyHeader'), t('estimateHeader')], rows);
    this.copyState = copied ? 'copied' : 'failed';
    clearTimeout(this.copyTimeout);
    this.copyTimeout = setTimeout(() => this.copyState = 'idle', 2000);
  }
}
