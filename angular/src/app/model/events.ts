export interface GameInfo {
  name: string;
  deck: string;
  revealed: boolean;
  /** Name of the story being estimated */
  story?: string;
  /** Number of stories estimated so far, per card value */
  estimates?: Record<string, number>;
  /** Stories estimated so far, oldest first */
  history?: HistoryEntry[];
  /** Sum of the estimates of the stories estimated so far */
  total?: number;
  /** What will be recorded when the current turn ends */
  finalEstimate?: FinalEstimate;
  playerId?: string;
}

export interface HistoryEntry {
  name: string;
  estimate: number;
}

export interface FinalEstimate {
  /** auto: most-picked card, skip: nothing is recorded, value: chosen by a player */
  mode: 'auto' | 'skip' | 'value';
  /** The estimate that will be recorded, null if there is none */
  value: number | null;
}

export type FinalEstimateChoice = 'auto' | 'skip' | number;

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
