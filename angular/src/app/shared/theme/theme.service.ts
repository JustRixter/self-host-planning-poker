import { Injectable } from '@angular/core';

export type ThemePreference = 'auto' | 'light' | 'dark';

const STORAGE_KEY = 'shpp-theme';
const ORDER: ThemePreference[] = ['auto', 'light', 'dark'];

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly media = window.matchMedia('(prefers-color-scheme: dark)');
  preference: ThemePreference = this.load();

  constructor() {
    this.apply();
    this.media.addEventListener('change', () => this.apply());
  }

  cycle(): void {
    this.preference = ORDER[(ORDER.indexOf(this.preference) + 1) % ORDER.length];
    try {
      localStorage.setItem(STORAGE_KEY, this.preference);
    } catch { /* storage unavailable: keep preference for this session only */ }
    this.apply();
  }

  private load(): ThemePreference {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return ORDER.includes(stored as ThemePreference) ? stored as ThemePreference : 'auto';
    } catch {
      return 'auto';
    }
  }

  private apply(): void {
    const dark = this.preference === 'dark' || (this.preference === 'auto' && this.media.matches);
    document.documentElement.setAttribute('data-bs-theme', dark ? 'dark' : 'light');
  }
}
