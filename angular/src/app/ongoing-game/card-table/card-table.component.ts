import { Component, OnDestroy, ChangeDetectionStrategy } from '@angular/core';
import { GameState } from '../../model/events';
import { Subscription } from 'rxjs';
import { Deck } from '../../model/deck';
import { CurrentGameService } from '../current-game.service';
import { DeparturesComponent } from '../departures/departures.component';
import { PlayerHandComponent } from './player-hand/player-hand.component';
import { KeyValuePipe } from '@angular/common';
import { TranslocoDirective } from '@jsverse/transloco';

@Component({
    selector: 'shpp-card-table',
    templateUrl: './card-table.component.html',
    styleUrls: ['./card-table.component.scss'],
    standalone: true,
    changeDetection: ChangeDetectionStrategy.Eager,
    imports: [TranslocoDirective, PlayerHandComponent, KeyValuePipe, DeparturesComponent]
})
export class CardTableComponent implements OnDestroy {
  state: GameState = {}
  /** With many players the cards get smaller so that the table and the card picker both fit on screen */
  compact = false;
  canReveal = true;
  deck?: Deck;

  private stateSubscription: Subscription;
  private revealedSubscription: Subscription;
  private deckSubscription: Subscription;

  constructor(private currentGameService: CurrentGameService) {
    this.stateSubscription = this.currentGameService.state$
    .subscribe((state: GameState) => {
      this.state = state;
      this.compact = Object.keys(state).length > 6;
    });

    this.deckSubscription = currentGameService.deck$
    .subscribe((deck: Deck) => this.deck = deck);

    this.revealedSubscription = currentGameService.revealed$
    .subscribe((revealed: boolean) => this.canReveal = !revealed)
  }

  revealCards(): void {
    this.currentGameService.revealCards();
  }

  endTurn(): void {
    this.currentGameService.endTurn();
  }

  ngOnDestroy(): void {
    this.stateSubscription.unsubscribe();
    this.revealedSubscription.unsubscribe();
    this.deckSubscription.unsubscribe();
  }
}
