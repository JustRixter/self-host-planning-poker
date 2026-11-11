import { Component, ChangeDetectionStrategy } from '@angular/core';
import { Deck } from '../model/deck';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { environment } from '../../environments/environment';
import { Router } from '@angular/router';
import { GameFormComponent } from '../shared/game-form/game-form.component';
import { ContainerComponent } from '../shared/container/container.component';
import { NavAppTitleComponent } from '../navigation-bar/app-title/nav-app-title.component';
import { FooterComponent } from '../shared/footer/footer.component';
import { PathLocationStrategy } from '@angular/common';
import { TranslocoService } from '@jsverse/transloco';
import { ToastService } from '../shared/toast/toast.service';

@Component({
  standalone: true,
  selector: 'shpp-new-game-page',
  templateUrl: './new-game-page.component.html',
  styleUrls: [ './new-game-page.component.scss' ],
  changeDetection: ChangeDetectionStrategy.Eager,
  imports: [
    GameFormComponent,
    ContainerComponent,
    NavAppTitleComponent,
    FooterComponent
  ]
})
export default class NewGamePageComponent {

  constructor(private http: HttpClient,
              private router: Router,
              private pls: PathLocationStrategy,
              private transloco: TranslocoService,
              private toastService: ToastService) { }

  onNewGame(newGame: {name: string, deck: Deck}): void {
    const body = {
      name: newGame.name,
      deck: newGame.deck.name
    }
    this.http.post(`${ environment.backendRootOverride ?? this.pls.getBaseHref() }create`, body, { responseType: 'text' })
      .subscribe({
        next: (gameId) => this.router.navigate(['game', gameId]),
        error: (error: HttpErrorResponse) => this.showError(error)
      });
  }

  private showError(error: HttpErrorResponse): void {
    const key = error.status === 429 ? 'errors.tooManyGames' : 'errors.createFailed';
    const minutes = Math.max(1, Math.ceil(Number(error.headers.get('Retry-After') ?? 60) / 60));
    this.toastService.show(this.transloco.translate(key, { minutes: minutes, status: error.status }),
      { className: 'bg-danger text-light' });
  }

}
