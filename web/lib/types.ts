export type GameLogEntry = {
  opponent: string;
  date: string;
  score: string;
  points: number;
  rebounds: number;
  assists: number;
  steals: number;
  above_avg: boolean;
  game_type: string;
};

export type Game = {
  id: string;
  date: string;
  opponent: string;
  our_team?: string | null;
  location?: string | null;
  result?: string | null;
  our_score?: number | null;
  opp_score?: number | null;
  notes?: string | null;
  game_type?: string | null;
  event_name?: string | null;
};

export type Report = {
  id: string;
  game_id?: string | null;
  opponent?: string | null;
  date?: string | null;
  report_type: string;
  report_text: string;
  created_at?: string;
};

export type OpponentPlayer = {
  id: string;
  opponent: string;
  player_number: string;
  player_name?: string | null;
  tendencies: string[];
  last_seen_date?: string | null;
};

export type CoachNote = {
  id: string;
  content: string;
  opponent?: string | null;
  date?: string | null;
  status?: string;
  created_at?: string;
  updated_at?: string;
};

export type Season = {
  id: string;
  name: string;
  team_name?: string | null;
  imported_at?: string;
};

export type PlayerCardData = {
  number: string | number;
  name: string;
  games_played: number;
  ppg: number;
  rpg: number;
  apg: number;
  spg: number;
  bpg: number;
  topg: number;
  l5_ppg: number;
  l5_rpg: number;
  l5_apg: number;
  l5_spg: number;
  fg_made: number;
  fg_attempted: number;
  fg_pct: number;
  three_made: number;
  three_attempted: number;
  three_pct: number;
  ft_made: number;
  ft_attempted: number;
  ft_pct: number;
  l5_fg_pct: number;
  l5_three_pct: number;
  l5_ft_pct: number;
  ppg_trend: number;
  rpg_trend: number;
  apg_trend: number;
  spg_trend: number;
  fg_trend: number;
  three_trend: number;
  ft_trend: number;
  type_counts: Record<string, number>;
  game_log: GameLogEntry[];
  source: string;
};
