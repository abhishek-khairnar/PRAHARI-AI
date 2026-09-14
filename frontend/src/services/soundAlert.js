/**
 * PRAHARI-AI Audio Notification Synthesizer
 * Uses native Web Audio API to produce crisp security alert chimes
 * without external audio dependencies or autoplay violation crashes.
 */

const SOUND_PREF_KEY = 'prahari_sound_enabled';

let audioCtx = null;

function getAudioContext() {
  if (!audioCtx && (window.AudioContext || window.webkitAudioContext)) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    audioCtx = new AudioContextClass();
  }
  return audioCtx;
}

export function isSoundEnabled() {
  const val = localStorage.getItem(SOUND_PREF_KEY);
  return val === null ? true : val === 'true';
}

export function setSoundEnabled(enabled) {
  localStorage.setItem(SOUND_PREF_KEY, enabled ? 'true' : 'false');
  if (enabled) {
    // Attempt to resume audio context if suspended
    const ctx = getAudioContext();
    if (ctx && ctx.state === 'suspended') {
      ctx.resume().catch(() => {});
    }
  }
}

/**
 * Play a synthesized alert tone tailored to incident severity.
 * Guaranteed safe: never throws unhandled errors or crashes UI.
 */
export function playAlertSound(severity = 'HIGH') {
  if (!isSoundEnabled()) return;

  try {
    const ctx = getAudioContext();
    if (!ctx) return;

    // Browser autoplay policy guard
    if (ctx.state === 'suspended') {
      return;
    }

    const sev = (severity || 'HIGH').toUpperCase();
    const now = ctx.currentTime;

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.connect(gain);
    gain.connect(ctx.destination);

    if (sev === 'CRITICAL') {
      // Rapid urgency two-tone alarm
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(880, now); // A5
      osc.frequency.setValueAtTime(1046.5, now + 0.12); // C6
      osc.frequency.setValueAtTime(880, now + 0.24);
      osc.frequency.setValueAtTime(1046.5, now + 0.36);

      gain.gain.setValueAtTime(0.2, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.5);

      osc.start(now);
      osc.stop(now + 0.5);
    } else if (sev === 'HIGH') {
      // Prominent single alert chime
      osc.type = 'sine';
      osc.frequency.setValueAtTime(659.25, now); // E5
      osc.frequency.exponentialRampToValueAtTime(880, now + 0.15); // A5

      gain.gain.setValueAtTime(0.18, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.4);

      osc.start(now);
      osc.stop(now + 0.4);
    } else if (sev === 'MEDIUM') {
      // Gentle notification ping
      osc.type = 'sine';
      osc.frequency.setValueAtTime(523.25, now); // C5

      gain.gain.setValueAtTime(0.12, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.25);

      osc.start(now);
      osc.stop(now + 0.25);
    }
  } catch (err) {
    console.debug('[SoundAlert] Audio playback suppressed:', err);
  }
}
