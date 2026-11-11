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
  /** Whether the players let AI agents in the game (through the MCP server, with its agent link) */
  agentAccess?: boolean;
  playerId?: string;
  /** Sent when joining: whether the server lets games turn on the access of AI agents */
  mcpAvailable?: boolean;
}

/** What an AI agent changed in the stories of the game */
export interface AgentActivity {
  action: 'added' | 'updated' | 'moved' | 'requeued' | 'deleted' | 'cleared';
  count?: number;
  story?: string;
}

/** The answer to the events about the agent link: null when agents are not let in */
export interface AgentLinkResponse {
  link: string | null;
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
