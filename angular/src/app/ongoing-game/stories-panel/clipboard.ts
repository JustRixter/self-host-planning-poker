function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** Tabs and line breaks would break the columns and rows of the pasted table */
function singleLine(text: string): string {
  return text.replace(/[\t\r\n]+/g, ' ').trim();
}

/**
 * Copies a table to the clipboard, both as tab-separated text (spreadsheets, text editors)
 * and as an HTML table (documents, wikis). Returns whether the copy succeeded.
 */
export async function copyTable(header: string[], rows: string[][]): Promise<boolean> {
  const all = [header, ...rows].map((row) => row.map(singleLine));
  const text = all.map((row) => row.join('\t')).join('\n');
  const html = '<table>'
    + `<thead><tr>${all[0].map((cell) => `<th>${escapeHtml(cell)}</th>`).join('')}</tr></thead>`
    + `<tbody>${all.slice(1).map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join('')}</tr>`).join('')}</tbody>`
    + '</table>';

  try {
    if (navigator.clipboard && typeof ClipboardItem !== 'undefined') {
      await navigator.clipboard.write([new ClipboardItem({
        'text/plain': new Blob([text], { type: 'text/plain' }),
        'text/html': new Blob([html], { type: 'text/html' })
      })]);
      return true;
    }
  } catch {
    // Fall through to the legacy way
  }
  return legacyCopy(text);
}

/** Copies plain text to the clipboard. Returns whether the copy succeeded. */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Fall through to the legacy way
  }
  return legacyCopy(text);
}

/** navigator.clipboard is only available on secure origins (HTTPS or localhost), and this app is often served over HTTP */
function legacyCopy(text: string): boolean {
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);
  textarea.select();
  try {
    return document.execCommand('copy');
  } catch {
    return false;
  } finally {
    document.body.removeChild(textarea);
  }
}
