export interface GameInfo {
  name: string;
  deck: string;
  revealed: boolean;
  /** Number of stories estimated so far, per card value */
  estimates?: Record<string, number>;
  playerId?: string;
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
