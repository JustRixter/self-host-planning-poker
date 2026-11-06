import { ChangeDetectionStrategy, Component, TemplateRef } from '@angular/core';
import { AsyncPipe } from '@angular/common';
import { NgbOffcanvas, NgbTooltip } from '@ng-bootstrap/ng-bootstrap';
import { TranslocoDirective } from '@jsverse/transloco';
import { map, Observable } from 'rxjs';
import { CurrentGameService } from '../../ongoing-game/current-game.service';
import { decksDict, displayCardValue } from '../../model/deck';

interface StoryRow {
  name: string;
  display: string | number;
}

interface StoriesView {
  stories: StoryRow[];
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

  constructor(currentGameService: CurrentGameService, private offcanvasService: NgbOffcanvas) {
    this.view$ = currentGameService.gameInfo$.pipe(
      map((info) => {
        const deck = info ? decksDict[info.deck] : undefined;
        return {
          stories: (info?.history ?? []).map((entry) => ({
            name: entry.name,
            display: (deck && displayCardValue(deck, entry.estimate)) ?? entry.estimate
          })),
          total: info?.total ?? 0,
          showPoints: !!deck && !deck.textValues
        };
      })
    );
  }

  open(content: TemplateRef<unknown>): void {
    this.offcanvasService.open(content, { ariaLabelledBy: 'stories-title', position: 'end' });
  }
}
