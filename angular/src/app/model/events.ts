export interface GameInfo {
  name: string;
  deck: string;
  revealed: boolean;
  /** Stories estimated so far (one per revealed turn), oldest first */
  history?: HistoryEntry[];
  /** Sum of the estimates of the stories estimated so far */
  total?: number;
  playerId?: string;
}

export interface HistoryEntry {
  id: number;
  name: string;
  estimate: number;
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
