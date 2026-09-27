const escape = '\u001b[';
const paint = (text, style) => `${escape}${style}m${text}${escape}0m`;

export function supportsColor(stream = process.stdout, env = process.env) {
  if (env.FORCE_COLOR === '0') return false;
  if (['', '1', '2', '3'].includes(env.FORCE_COLOR)) return true;
  if (env.NO_COLOR) return false;
  return Boolean(stream.isTTY && env.TERM !== 'dumb');
}

// Match the original text once, so ANSI escapes never become highlighting input.
const tokens = /`[^`\n]+`|"(?:\\.|[^"\\])*"|https?:\/\/[^\s)]+|\bSODA_[A-Z0-9_]+\b|(?<![\w-])--?[a-z][\w-]*|\bsoda(?:[ \t]+(?:help|compile|html|check|theme|example|init)){0,2}|\bcd(?= )|<[^>\n]+>/g;

function inline(text) {
  return text.replace(tokens, (token, offset) => {
    if (token.startsWith('"')) {
      return paint(token, /^\s*:/.test(text.slice(offset + token.length)) ? '33' : '32');
    }
    if (token.startsWith('http')) return paint(token, '4;36');
    if (/^(?:-+|SODA_|<)/.test(token)) return paint(token, '33');
    return paint(token, '36');
  });
}

export function formatHelp(text, color = supportsColor()) {
  if (!color) return text;
  return text.split('\n').map(line => {
    if (/^SODA\b/.test(line) || /^#{1,6} /.test(line) || /^\S.*[：:]$/.test(line)) {
      return paint(line, '1;36');
    }
    if (/^```/.test(line) || /^\|[ :|\-]+\|$/.test(line)) return paint(line, '2');
    const field = /^( {2,})([a-z][a-z_]*)(?= {2,})/.exec(line);
    if (field) return field[1] + paint(field[2], '33') + inline(line.slice(field[0].length));
    return inline(line);
  }).join('\n');
}

export function writeHelp(text) {
  process.stdout.write(formatHelp(text));
}
