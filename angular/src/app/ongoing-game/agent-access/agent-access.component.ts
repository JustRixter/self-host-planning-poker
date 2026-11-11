import { ChangeDetectionStrategy, Component, OnDestroy } from '@angular/core';
import { AsyncPipe, PathLocationStrategy } from '@angular/common';
import { TranslocoDirective, TranslocoService } from '@jsverse/transloco';
import { combineLatest, distinctUntilChanged, map, Observable, Subscription } from 'rxjs';
import { CurrentGameService } from '../current-game.service';
import { copyText } from '../stories-panel/clipboard';
import { environment } from '../../../environments/environment';

interface AgentAccessView {
  /** The server lets games turn on the access of AI agents */
  available: boolean;
  enabled: boolean;
}

/**
 * Lets the players turn on the access of AI agents to the game: an agent connected to the MCP server of the app can
 * then read and prepare the stories, with the agent link of the game. Every player sees whether it is on.
 */
@Component({
  standalone: true,
  selector: 'shpp-agent-access',
  templateUrl: './agent-access.component.html',
  styleUrl: './agent-access.component.scss',
  changeDetection: ChangeDetectionStrategy.Eager,
  imports: [TranslocoDirective, AsyncPipe]
})
export class AgentAccessComponent implements OnDestroy {
  view$: Observable<AgentAccessView>;
  /** The agent link, once fetched: agents are let in */
  link: string | null = null;
  busy = false;
  copied: 'link' | 'server' | null = null;
  readonly serverUrl: string;

  private subscription: Subscription;
  private copyTimeout?: ReturnType<typeof setTimeout>;

  constructor(private currentGameService: CurrentGameService,
              private transloco: TranslocoService,
              pls: PathLocationStrategy) {
    this.serverUrl = `${environment.backendRootOverride ?? window.location.origin + pls.getBaseHref()}mcp`;
    const enabled$ = currentGameService.gameInfo$.pipe(map((info) => !!info?.agentAccess), distinctUntilChanged());
    this.view$ = combineLatest([currentGameService.mcpAvailable$, enabled$])
      .pipe(map(([available, enabled]) => ({ available, enabled })));
    // Every player can show the link: fetch it when agents are let in, forget it when they are not anymore
    this.subscription = enabled$.subscribe((enabled) => {
      if (enabled) {
        this.currentGameService.getAgentLink().then((link) => this.link = link);
      } else {
        this.link = null;
      }
    });
  }

  async enable(): Promise<void> {
    this.busy = true;
    this.link = await this.currentGameService.enableAgentAccess();
    this.busy = false;
  }

  async renew(): Promise<void> {
    if (confirm(this.transloco.translate('agentAccess.renewConfirm'))) {
      this.busy = true;
      this.link = await this.currentGameService.renewAgentLink();
      this.busy = false;
    }
  }

  disable(): void {
    if (confirm(this.transloco.translate('agentAccess.disableConfirm'))) {
      this.currentGameService.disableAgentAccess();
    }
  }

  async copy(what: 'link' | 'server'): Promise<void> {
    const text = what === 'link' ? this.link : this.serverUrl;
    if (text && await copyText(text)) {
      this.copied = what;
      clearTimeout(this.copyTimeout);
      this.copyTimeout = setTimeout(() => this.copied = null, 2000);
    }
  }

  ngOnDestroy(): void {
    this.subscription.unsubscribe();
    clearTimeout(this.copyTimeout);
  }
}
