import { Component, DestroyRef, ElementRef, ViewChild, inject, ChangeDetectionStrategy } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AsyncPipe } from '@angular/common';
import { TranslocoDirective } from '@jsverse/transloco';
import { map, Observable } from 'rxjs';
import { CurrentGameService } from '../current-game.service';

@Component({
  standalone: true,
  selector: 'shpp-story-name',
  imports: [TranslocoDirective, AsyncPipe],
  changeDetection: ChangeDetectionStrategy.Eager,
  template: `
    <div class="container pb-3" *transloco="let t; read 'story'">
      <input #input type="text" class="form-control form-control-sm mx-auto" style="max-width: 28rem" maxlength="100"
             [attr.aria-label]="t('label')"
             [placeholder]="t('placeholder')"
             [value]="(story$ | async) ?? ''"
             (change)="save(input.value)"
             (keyup.enter)="input.blur()">
    </div>
  `
})
export class StoryNameComponent {
  story$: Observable<string>;

  @ViewChild('input')
  private input?: ElementRef<HTMLInputElement>;

  constructor(private currentGameService: CurrentGameService) {
    this.story$ = currentGameService.gameInfo$.pipe(map((info) => info?.story ?? ''));
    // The story name of the previous turn is forgotten by the server: make sure that unsaved text is cleared too
    currentGameService.newGame$
      .pipe(takeUntilDestroyed(inject(DestroyRef)))
      .subscribe(() => {
        if (this.input) {
          this.input.nativeElement.value = '';
        }
      });
  }

  save(name: string): void {
    this.currentGameService.setStoryName(name);
  }
}
