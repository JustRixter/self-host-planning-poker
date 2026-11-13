import { AfterViewInit, ChangeDetectionStrategy, Component, ElementRef, HostListener, NgZone, OnDestroy, ViewChild } from '@angular/core';
import { GameState } from '../../model/events';
import { Subscription } from 'rxjs';
import { Deck } from '../../model/deck';
import { CurrentGameService } from '../current-game.service';
import { DeparturesComponent } from '../departures/departures.component';
import { PlayerHandComponent } from './player-hand/player-hand.component';
import { KeyValuePipe } from '@angular/common';
import { TranslocoDirective } from '@jsverse/transloco';
import { drawTableGlow } from './table-glow';

/** Rough footprint of a full-size hand (card + name + margins), in px */
const HAND_WIDTH = { narrow: 100, wide: 140 };
const HAND_HEIGHT = { narrow: 140, wide: 156 };
/** Height taken by everything that is not the table: navbar, buttons, card picker */
const RESERVED_HEIGHT = 380;
/** Bootstrap's `md` breakpoint, where the hands get wider margins */
const MD_BREAKPOINT = 768;

@Component({
    selector: 'shpp-card-table',
    templateUrl: './card-table.component.html',
    styleUrls: ['./card-table.component.scss'],
    standalone: true,
    changeDetection: ChangeDetectionStrategy.Eager,
    imports: [TranslocoDirective, PlayerHandComponent, KeyValuePipe, DeparturesComponent]
})
export class CardTableComponent implements AfterViewInit, OnDestroy {
  state: GameState = {}
  /**
   * When the full-size hands would not fit on screen next to the card picker, the cards get smaller.
   * Depends on the screen size: a big screen fits many players at full size.
   */
  compact = false;

  canReveal = true;
  deck?: Deck;

  @ViewChild('seats') private seats?: ElementRef<HTMLElement>;
  @ViewChild('glow') private glow?: ElementRef<HTMLCanvasElement>;
  private resizeObserver?: ResizeObserver;
  private glowResizeObserver?: ResizeObserver;
  private themeObserver?: MutationObserver;
  private glowFrame?: number;

  private stateSubscription: Subscription;
  private revealedSubscription: Subscription;
  private deckSubscription: Subscription;

  constructor(private currentGameService: CurrentGameService, private zone: NgZone, private host: ElementRef<HTMLElement>) {
    this.stateSubscription = this.currentGameService.state$
    .subscribe((state: GameState) => {
      this.state = state;
      this.updateCompact();
    });

    this.deckSubscription = currentGameService.deck$
    .subscribe((deck: Deck) => this.deck = deck);

    this.revealedSubscription = currentGameService.revealed$
    .subscribe((revealed: boolean) => this.canReveal = !revealed)
  }

  ngAfterViewInit(): void {
    if (typeof ResizeObserver !== 'undefined' && this.seats) {
      // Fires once right away, then on every size change. It runs outside Angular's zone,
      // so re-enter it only when the layout actually has to change
      this.resizeObserver = new ResizeObserver(() => {
        const compact = this.computeCompact();
        if (compact !== this.compact) {
          this.zone.run(() => this.compact = compact);
        }
      });
      this.resizeObserver.observe(this.seats.nativeElement);
    }
    this.watchGlow();
  }

  /** Paints the light on the table again whenever its size or the theme changes */
  private watchGlow(): void {
    const canvas = this.glow?.nativeElement;
    if (!canvas || typeof ResizeObserver === 'undefined' || typeof MutationObserver === 'undefined') {
      return;
    }
    this.zone.runOutsideAngular(() => {
      // At most once per frame, however many changes arrive
      const redraw = () => {
        if (this.glowFrame === undefined) {
          this.glowFrame = requestAnimationFrame(() => {
            this.glowFrame = undefined;
            drawTableGlow(canvas, this.host.nativeElement);
          });
        }
      };
      this.glowResizeObserver = new ResizeObserver(redraw);
      this.glowResizeObserver.observe(canvas);
      // The theme is switched with an attribute on <html>; overrides may also use a class or inline style
      this.themeObserver = new MutationObserver(redraw);
      this.themeObserver.observe(document.documentElement, { attributeFilter: ['data-bs-theme', 'class', 'style'] });
    });
  }

  @HostListener('window:resize')
  updateCompact(): void {
    this.compact = this.computeCompact();
  }

  private computeCompact(): boolean {
    const players = Object.keys(this.state).length;
    const element = this.seats?.nativeElement;
    if (!element || typeof window === 'undefined') {
      return players > 6;
    }
    // The width of the seats does not depend on the cards (they wrap), but their height does,
    // so the height comes from the window to avoid flipping back and forth
    const wide = window.innerWidth >= MD_BREAKPOINT;
    const perRow = Math.max(1, Math.floor(element.clientWidth / (wide ? HAND_WIDTH.wide : HAND_WIDTH.narrow)));
    const rows = Math.max(1, Math.floor((window.innerHeight - RESERVED_HEIGHT) / (wide ? HAND_HEIGHT.wide : HAND_HEIGHT.narrow)));
    return players > perRow * rows;
  }

  revealCards(): void {
    this.currentGameService.revealCards();
  }

  endTurn(): void {
    this.currentGameService.endTurn();
  }

  ngOnDestroy(): void {
    this.resizeObserver?.disconnect();
    this.glowResizeObserver?.disconnect();
    this.themeObserver?.disconnect();
    if (this.glowFrame !== undefined) {
      cancelAnimationFrame(this.glowFrame);
    }
    this.stateSubscription.unsubscribe();
    this.revealedSubscription.unsubscribe();
    this.deckSubscription.unsubscribe();
  }
}
