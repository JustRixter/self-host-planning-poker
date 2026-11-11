export interface GameInfo {
  name: string;
  deck: string;
  revealed: boolean;
  /** Stories estimated so far (one per revealed turn), oldest first */
  history?: HistoryEntry[];
  /** Sum of the estimates of the stories estimated so far */
  total?: number;
  /** Stories waiting to be estimated: the first one is estimated at the next reveal */
  backlog?: Story[];
  /** The story being estimated: the next one of the backlog, or the one the revealed turn has just estimated */
  current?: Story | HistoryEntry | null;
  playerId?: string;
}

export interface Story {
  id: number;
  name: string;
  /** Key of the issue in a tracker, such as ABC-123 */
  ref?: string | null;
  /** Link to the issue (always http or https) */
  url?: string | null;
}

export interface Vote {
  player: string;
  card: number;
}

export interface HistoryEntry extends Story {
  estimate: number;
  votes?: Vote[];
}

export interface NewStory {
  name: string;
  ref?: string;
  url?: string;
}

export interface Player {
  name: string;
  spectator: boolean;
}

export interface PlayerState extends Player {
  hasPicked?: boolean;
  hand?: number;
}

export type GameState = Record<string, PlayerState>;

export interface ErrorMessage {
  error: true;
  message: string;
  code: number;
}
