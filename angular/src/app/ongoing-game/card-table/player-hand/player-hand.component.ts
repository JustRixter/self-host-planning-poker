import { Component, Input, ChangeDetectionStrategy } from '@angular/core';
import { PlayerState } from '../../../model/events';
import { Deck, displayCardValue } from '../../../model/deck';

import { TranslocoDirective } from '@jsverse/transloco';

@Component({
    selector: 'shpp-player-hand',
    templateUrl: './player-hand.component.html',
    styleUrls: ['./player-hand.component.scss'],
    standalone: true,
    changeDetection: ChangeDetectionStrategy.Eager,
    imports: [TranslocoDirective]
})
export class PlayerHandComponent {
  @Input() playerState?: PlayerState;
  @Input() deck?: Deck;

  displayCardValue = displayCardValue;
}
