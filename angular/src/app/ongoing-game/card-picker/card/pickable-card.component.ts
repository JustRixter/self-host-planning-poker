import { Component, Input, ChangeDetectionStrategy } from '@angular/core';
import { CardValue } from '../../../model/deck';

@Component({
    selector: 'shpp-pickable-card',
    templateUrl: './pickable-card.component.html',
    styleUrls: ['./pickable-card.component.scss'],
    changeDetection: ChangeDetectionStrategy.Eager,
    standalone: true
})
export class PickableCardComponent {
  @Input() cardValue?: CardValue;
  @Input() selected = false;
  @Input() disabled = false;

}
