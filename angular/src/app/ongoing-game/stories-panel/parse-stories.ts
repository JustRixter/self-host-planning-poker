import { NewStory } from '../../model/events';

/** Same limits as the server: longer texts are cut there, longer lists do not fit in the backlog */
const MAX_NAME_LENGTH = 100;
const MAX_STORIES = 200;

/** Issue keys of trackers such as Jira or Linear: ABC-123 */
const REF_AT_START = /^([A-Z][A-Z0-9_]*-\d+)\b[\s:–—-]*/;
const REF_ANYWHERE = /\b([A-Z][A-Z0-9_]*-\d+)\b/;
const URL = /https?:\/\/\S+/;
/** List markers left by a copy from a document: "- ", "* ", "• ", "1. ", "2) " */
const LIST_MARKER = /^(?:[-*•]|\d+[.)])\s+/;

/**
 * Reads the stories pasted in the backlog, one per line. A line can start with the key of the issue
 * ("ABC-123 Login timeout" or "ABC-123: Login timeout") and hold a link to it.
 */
export function parseStories(text: string): NewStory[] {
  return text.split(/\r?\n/)
    .map((line) => parseLine(line))
    .filter((story): story is NewStory => story !== null)
    .slice(0, MAX_STORIES);
}

function parseLine(line: string): NewStory | null {
  let rest = line.trim().replace(LIST_MARKER, '');
  const url = rest.match(URL)?.[0];
  if (url) {
    rest = rest.replace(url, ' ');
  }
  rest = rest.replace(/\s+/g, ' ').trim();

  let ref = rest.match(REF_AT_START)?.[1];
  if (ref) {
    rest = rest.replace(REF_AT_START, '');
  } else if (url) {
    // A link such as https://jira.example.com/browse/ABC-123 tells the key of the issue
    ref = url.match(REF_ANYWHERE)?.[1];
  }

  const name = rest.slice(0, MAX_NAME_LENGTH);
  if (!name && !ref) {
    return null;
  }
  const story: NewStory = { name: name };
  if (ref) {
    story.ref = ref;
  }
  if (url) {
    story.url = url;
  }
  return story;
}
