import { inject, Injectable } from '@angular/core';
import { Manager, Socket } from 'socket.io-client';
import { environment } from '../../environments/environment';
import { BehaviorSubject, distinctUntilChanged, filter, map, Observable, Subject } from 'rxjs';
import { ErrorMessage, GameInfo, GameState, NewStory } from '../model/events';
import { Deck, decksDict } from '../model/deck';
import { ActivatedRouteSnapshot, CanActivateFn, Router, UrlTree } from '@angular/router';
import { TranslocoService } from '@jsverse/transloco';
import { UserInformationService } from '../shared/user-info/user-information.service';
import { ToastService } from '../shared/toast/toast.service';
import { PathLocationStrategy } from '@angular/common';

/** reconnecting: the connection was lost and the client keeps trying. failed: it gave up, the page has to be reloaded */
export type ConnectionState = 'connected' | 'reconnecting' | 'failed';

@Injectable({
  providedIn: 'root'
})
export class CurrentGameService {
  private readonly totalAttempts = 10;
  private readonly reconnectDelaySeconds = 5;
  private readonly retries = 5;
  private readonly ackTimeoutMs = 10000;

  private manager: Manager;
  private socket: Socket;

  private stateSubject = new BehaviorSubject<GameState>({});
  private infoSubject = new BehaviorSubject<GameInfo | null>(null);
  private newGameSubject = new Subject<void>();
  private departuresSubject = new Subject<string>();
  private connectionSubject = new BehaviorSubject<ConnectionState>('connected');

  /** The game we are in: after a lost connection, we have to join it again */
  private gameId?: string;
  /** The card we have picked, to pick it again after rejoining */
  private lastPick: number | null = null;

  constructor(private router: Router,
              private userInformation: UserInformationService,
              private transloco: TranslocoService,
              private toastService: ToastService,
              private pls: PathLocationStrategy) {
    this.manager = new Manager(environment.backendRootOverride ?? window.location.origin,
      {
        path: `${this.pls.getBaseHref()}socket.io/`,
        autoConnect: false,
        reconnection: true,
        reconnectionDelay: this.reconnectDelaySeconds * 1000,
        reconnectionAttempts: this.totalAttempts
      });
    this.socket = this.manager.socket('/', {
      retries: this.retries,
      ackTimeout: this.ackTimeoutMs
    });

    this.socket.on('state', (state: GameState) => {
      this.notifyDepartures(this.stateSubject.value, state);
      this.stateSubject.next(state);
    });
    this.socket.on('info', (info: GameInfo) => {
      if (info.deck !== this.infoSubject.value?.deck) {
        // The server clears the hands when the deck changes
        this.lastPick = null;
      }
      this.infoSubject.next(info);
    });
    this.socket.on('new_game', () => {
      this.lastPick = null;
      this.newGameSubject.next();
    });

    // A connection that comes back is a new connection for the server, which has removed us from the game
    this.socket.on('connect', () => {
      this.connectionSubject.next('connected');
      this.rejoin();
    });

    this.socket.on('disconnect', (reason) => {
      console.info(`Socket disconnected. Reason is "${reason}"`);
      if (reason === 'io client disconnect') {
        return; // we left the game on purpose
      }
      this.connectionSubject.next('reconnecting');
      if (reason === 'io server disconnect') {
        // The server closed the connection: the client does not try to reconnect by itself in that case
        this.socket.connect();
      }
    });
    // No toasts for the state of the connection: the navigation bar shows an icon when there is a problem
    this.manager.on('reconnect_attempt', (attempt: number) => {
      console.info(`Reconnection attempt ${attempt}/${this.totalAttempts}`);
      this.connectionSubject.next('reconnecting');
    });
    this.manager.on('reconnect_error', (err: Error) => console.warn(`Could not reconnect: ${err.message}`));
    this.manager.on('reconnect_failed', () => {
      console.error(`Could not reconnect after ${this.totalAttempts} attempts`);
      this.connectionSubject.next('failed');
    });

    this.userInformation.nameObservable().subscribe((name: string) => {
      if (this.socket.connected) {
        this.socket.emit('set_player_name', {name: name});
      }
    });
    this.userInformation.spectatorObservable().subscribe((spectator: boolean) => {
      if (this.socket.connected) {
        this.lastPick = null; // the server clears the hand of a player who changes role
        this.socket.emit('set_spectator', {spectator: spectator})
      }
    });
  }

  public get state$(): Observable<GameState> {
    return this.stateSubject.asObservable();
  }

  public get gameInfo$(): Observable<GameInfo | null> {
    return this.infoSubject.asObservable();
  }

  /** The state of the connection to the server, while we are in a game */
  public get connection$(): Observable<ConnectionState> {
    return this.connectionSubject.asObservable();
  }

  /** Emits the name of each player who leaves the game while we are in it */
  public get departures$(): Observable<string> {
    return this.departuresSubject.asObservable();
  }

  public get newGame$(): Observable<void>{
    return this.newGameSubject.asObservable();
  }

  public get revealed$(): Observable<boolean> {
    return this.gameInfo$.pipe(
      map((info: GameInfo | null) => info !== null ? info.revealed : false)
    );
  }

  /** Emits when the deck changes, not each time the info of the game does (a story edited, the cards revealed...) */
  public get deck$(): Observable<Deck> {
    return this.infoSubject.asObservable()
    .pipe(
      filter((gameInfo: GameInfo | null): gameInfo is GameInfo => gameInfo !== null),
      map((gameInfo: GameInfo) => decksDict[gameInfo?.deck]),
      distinctUntilChanged()
    );
  }

  canActivate(route: ActivatedRouteSnapshot): Promise<boolean | UrlTree> {
    const gameId = route.params['gameId'];
    return this.socket.connect()
    .emitWithAck('join', {
      game: gameId,
      name: this.userInformation.getName(),
      spectator: this.userInformation.isSpectator()
    })
    .then((response: GameInfo | ErrorMessage) => {
        if ('error' in response) {
          this.socket.disconnect();
          this.handleError(response);
          return this.router.parseUrl('/');
        } else {
          this.gameId = gameId;
          this.infoSubject.next(response);
          this.userInformation.setPlayerIdSubject(response.playerId);
          return true;
        }
      },
      (reason: any) => {
        this.handleError(reason);
        return this.router.parseUrl('/');
      });
  }

  /** Joins the game again after the connection was lost (and restored), and picks the card again */
  private rejoin(): void {
    const gameId = this.gameId;
    if (!gameId) {
      return; // the first connection: canActivate() joins the game
    }
    this.socket.emitWithAck('join', {
      game: gameId,
      name: this.userInformation.getName(),
      spectator: this.userInformation.isSpectator()
    })
    .then((response: GameInfo | ErrorMessage) => {
        if ('error' in response) {
          this.handleError(response);
          this.leave();
          this.router.navigateByUrl('/');
          return;
        }
        this.infoSubject.next(response);
        this.userInformation.setPlayerIdSubject(response.playerId);
        if (this.lastPick !== null && !response.revealed) {
          this.socket.emit('pick_card', { card: this.lastPick }, (error?: ErrorMessage) => this.handleError(error));
        }
      },
      (reason: any) => this.handleError(reason));
  }

  private notifyDepartures(previous: GameState, current: GameState): void {
    const currentNames = new Set(Object.values(current).map((player) => player.name));
    Object.entries(previous)
      .filter(([id]) => !(id in current))
      // Someone who reloads the page comes back under a new id: that is not worth announcing
      .filter(([, player]) => !currentNames.has(player.name))
      .forEach(([, player]) => this.departuresSubject.next(player.name));
  }

  public leave(): void {
    this.connectionSubject.next('connected');
    this.gameId = undefined;
    this.lastPick = null;
    this.socket.disconnect();
    this.stateSubject.next({});
    this.infoSubject.next(null);
  }

  public renameGame(newName: string): void {
    this.socket.emit('rename_game', { name: newName }, (response?: ErrorMessage) => this.handleError(response));
  }

  public setDeck(deck: Deck): void {
    this.socket.emit('set_deck', { deck: deck.name }, (response?: ErrorMessage) => this.handleError(response));
  }

  public updateStory(id: number, changes: { name?: string; estimate?: number }): void {
    this.socket.emit('update_story', { id: id, ...changes }, (response?: ErrorMessage) => this.handleError(response));
  }

  public deleteStory(id: number): void {
    this.socket.emit('delete_story', { id: id }, (response?: ErrorMessage) => this.handleError(response));
  }

  public addToBacklog(stories: NewStory[]): void {
    this.socket.emit('add_to_backlog', { stories: stories }, (response?: ErrorMessage) => this.handleError(response));
  }

  /** position starts at 1: the next story to estimate */
  public moveStory(id: number, position: number): void {
    this.socket.emit('move_story', { id: id, position: position }, (response?: ErrorMessage) => this.handleError(response));
  }

  /** Sends the next story of the backlog to the end of it */
  public skipStory(): void {
    this.socket.emit('skip_story', (response?: ErrorMessage) => this.handleError(response));
  }

  /** Puts an estimated story back on top of the backlog, to vote on it again */
  public requeueStory(id: number): void {
    this.socket.emit('requeue_story', { id: id }, (response?: ErrorMessage) => this.handleError(response));
  }

  public clearBacklog(): void {
    this.socket.emit('clear_backlog', (response?: ErrorMessage) => this.handleError(response));
  }

  public pickCard(cardValue: number | null): void {
    this.lastPick = cardValue;
    this.socket.emit('pick_card', { card: cardValue }, (response?: ErrorMessage) => this.handleError(response));
  }

  public revealCards(): void {
    this.socket.emit('reveal_cards', (response?: ErrorMessage) => this.handleError(response));
  }

  public endTurn(): void {
    this.socket.emit('end_turn', (response?: ErrorMessage) => this.handleError(response));
  }

  private handleError(error?: ErrorMessage | any): void {
    if (error) {
      if ('error' in error) {
        this.error(`errors.${error.code}`, { message: error.message });
      } else {
        this.error(`errors.0`, { message: error });
      }
    }
  }

  private error(key: string, translateParams?: Record<string, unknown>): void {
    this.transloco.selectTranslate(key, translateParams).subscribe((text) => {
      console.error(text);
      this.toastService.show(text, { className: 'bg-danger text-light' });
    })
  }

}

export const canActivateGame: CanActivateFn = (route: ActivatedRouteSnapshot) => {
  return inject(CurrentGameService).canActivate(route);
}
