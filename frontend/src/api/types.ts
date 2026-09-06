/* Mirrors app/schemas.py. Keep the two in sync by hand. */

export interface Reciter {
  id: number;
  slug: string;
  name: string;
  description: string;
}

export interface Word {
  word_index: number;
  arabic_text: string;
  start_ms: number;
  end_ms: number;
}

export interface PassageVerse {
  verse_number: number;
  verse_key: string;
  arabic_text: string;
  words: Word[];
  start_ms: number;
  end_ms: number;
}

export interface Passage {
  reciter_slug: string;
  surah: string;
  reference_audio_url: string;
  verses: PassageVerse[];
}

export interface PitchOverlay {
  time_axis: number[];
  reference_semitones: number[];
  user_semitones_aligned: number[];
}

export interface Tip {
  verse: number;
  word_index: number | null;
  type: string;
  text: string;
}

export interface PerVerse {
  verse: number;
  score: number;
}

export interface Attempt {
  attempt_id: string;
  reciter_id: number;
  start_verse: number;
  end_verse: number;
  overall_score: number;
  label: string;
  sub_scores: Record<string, number>;
  per_verse: PerVerse[];
  pitch_overlay: PitchOverlay;
  tips: Tip[];
  created_at: string;
}

export interface AttemptSummary {
  attempt_id: string;
  reciter_id: number;
  reciter_slug: string;
  start_verse: number;
  end_verse: number;
  overall_score: number;
  label: string;
  created_at: string;
}

export interface User {
  id: number;
  email: string;
}
