/**
 * Draws the soft light on the card table into a canvas.
 *
 * The light is so faint that it spans only a few colour levels. As a CSS gradient, browsers round
 * each pixel to the nearest level; Chrome hides the steps with dithering, but Firefox does not,
 * so the light shows as rings. Here every pixel gets its final colour over the page background,
 * plus a little noise before the rounding, so the light fades smoothly in every browser.
 */

/** The same shape as the CSS gradient under the canvas: `ellipse 65% 75% at 50% 42%`, fading out at 72% */
const CENTRE_X = .5;
const CENTRE_Y = .42;
const RADIUS_X = .65;
const RADIUS_Y = .75;
const END = .72;

type Rgba = [number, number, number, number];

/** Reads a computed colour: `rgb()`/`rgba()`, or `color(srgb …)`, which some browsers return for newer syntaxes */
function parseColor(value: string): Rgba | undefined {
  const numbers = value.match(/-?[\d.]+(e-?\d+)?%?/gi)?.map(part =>
    part.endsWith('%') ? parseFloat(part) / 100 : parseFloat(part));
  if (!numbers || numbers.length < 3 || numbers.some(isNaN)) {
    return undefined;
  }
  if (value.startsWith('rgb')) {
    return [numbers[0], numbers[1], numbers[2], numbers[3] ?? 1];
  }
  if (value.startsWith('color(srgb')) {
    return [numbers[0] * 255, numbers[1] * 255, numbers[2] * 255, numbers[3] ?? 1];
  }
  return undefined;
}

/** The colour the table sits on: the background of the nearest ancestor that paints one */
function backgroundBehind(element: HTMLElement): Rgba | undefined {
  for (let current = element.parentElement; current; current = current.parentElement) {
    const color = parseColor(getComputedStyle(current).backgroundColor);
    if (color && color[3] > 0) {
      return color[3] === 1 ? color : undefined;
    }
  }
  return undefined;
}

/**
 * Paints the light. The canvas takes its colour from its CSS `color`.
 * Returns false when the colours cannot be read: the canvas is then left empty and the CSS gradient shows.
 */
export function drawTableGlow(canvas: HTMLCanvasElement, host: HTMLElement): boolean {
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  const glow = parseColor(getComputedStyle(canvas).color);
  const background = backgroundBehind(host);
  const context = canvas.getContext('2d');
  canvas.width = width;
  canvas.height = height;
  if (!glow || !background || !context || width === 0 || height === 0) {
    return false;
  }

  const image = context.createImageData(width, height);
  const pixels = image.data;
  const opacity = glow[3];
  for (let y = 0; y < height; y++) {
    const dy = ((y + .5) / height - CENTRE_Y) / RADIUS_Y;
    for (let x = 0; x < width; x++) {
      const dx = ((x + .5) / width - CENTRE_X) / RADIUS_X;
      const fade = 1 - Math.sqrt(dx * dx + dy * dy) / END;
      if (fade <= 0) {
        // Left transparent: the page background shows through
        continue;
      }
      const amount = fade * opacity;
      // Triangular noise of ±1 level: the average of each area keeps the exact colour.
      // The pixel array rounds to the nearest level and clamps by itself
      const noise = Math.random() - Math.random();
      const i = (y * width + x) * 4;
      for (let channel = 0; channel < 3; channel++) {
        pixels[i + channel] = background[channel] + amount * (glow[channel] - background[channel]) + noise;
      }
      pixels[i + 3] = 255;
    }
  }
  context.putImageData(image, 0, 0);
  return true;
}
