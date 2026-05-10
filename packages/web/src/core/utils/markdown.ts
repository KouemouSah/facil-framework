/**
 * Shared Markdown Renderer
 *
 * Converts markdown text to safe HTML for rendering with dangerouslySetInnerHTML.
 * Used by chatbot MessageItem and admin assistant components.
 *
 * Supports: bold, italic, code blocks, inline code, lists, links, headings, tables.
 * Sanitizes HTML entities to prevent XSS.
 *
 * @module core/utils/markdown
 */

/**
 * Sanitize HTML entities to prevent XSS injection
 */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Parse a markdown table block into styled HTML table.
 *
 * Expects format:
 *   | Header1 | Header2 |
 *   |---------|---------|
 *   | cell1   | cell2   |
 *
 * Supports alignment via separator row:
 *   :--- left, ---: right, :---: center
 */
function parseTable(tableBlock: string): string {
  const lines = tableBlock.trim().split('\n').filter(l => l.trim());
  if (lines.length < 2) return tableBlock;

  const parseRow = (line: string): string[] =>
    line.split('|').slice(1, -1).map(c => c.trim());

  const headerCells = parseRow(lines[0]);

  // Detect separator row and alignment
  const sepLine = lines[1];
  const isSeparator = /^\|[\s:]*-+[\s:]*(\|[\s:]*-+[\s:]*)*\|?\s*$/.test(sepLine);
  if (!isSeparator) return tableBlock;

  const sepCells = parseRow(sepLine);
  const alignments: string[] = sepCells.map(cell => {
    const trimmed = cell.trim();
    if (trimmed.startsWith(':') && trimmed.endsWith(':')) return 'center';
    if (trimmed.endsWith(':')) return 'right';
    return 'left';
  });

  const alignStyle = (i: number) => {
    const a = alignments[i] || 'left';
    return a !== 'left' ? ` style="text-align:${a}"` : '';
  };

  // Build header
  const thCells = headerCells
    .map((h, i) => `<th class="px-3 py-2 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider border-b bg-muted/50"${alignStyle(i)}>${h}</th>`)
    .join('');
  const thead = `<thead><tr>${thCells}</tr></thead>`;

  // Build body rows
  const bodyLines = lines.slice(2);
  const tbodyRows = bodyLines.map((line, rowIdx) => {
    const cells = parseRow(line);
    const tds = headerCells
      .map((_, i) => `<td class="px-3 py-1.5 text-sm border-b"${alignStyle(i)}>${cells[i] ?? ''}</td>`)
      .join('');
    const stripe = rowIdx % 2 === 1 ? ' class="bg-muted/30"' : '';
    return `<tr${stripe}>${tds}</tr>`;
  }).join('');
  const tbody = `<tbody>${tbodyRows}</tbody>`;

  return `<div class="overflow-x-auto my-3 rounded-md border"><table class="w-full text-sm">${thead}${tbody}</table></div>`;
}

/**
 * Render markdown text to safe HTML string.
 *
 * @param text - Raw markdown text (from LLM or user)
 * @returns HTML string safe for dangerouslySetInnerHTML
 */
export function renderMarkdown(text: string): string {
  // Step 1: Extract code blocks and tables BEFORE escaping (they need special handling)
  const codeBlocks: string[] = [];
  const tableBlocks: string[] = [];

  // Extract fenced code blocks first
  let processed = text.replace(/```([\s\S]*?)```/g, (_match, code) => {
    const idx = codeBlocks.length;
    codeBlocks.push(code);
    return `%%CODEBLOCK_${idx}%%`;
  });

  // Extract markdown tables (consecutive lines starting/ending with |)
  processed = processed.replace(
    /(?:^|\n)((?:\|[^\n]+\|\s*\n){2,})/g,
    (_match, tableText: string, offset: number) => {
      // Only replace if starts at line boundary
      const prefix = offset > 0 && processed[offset - 1] !== '\n' ? '\n' : '';
      const idx = tableBlocks.length;
      tableBlocks.push(tableText);
      return `${prefix}%%TABLE_${idx}%%`;
    }
  );

  // Step 2: Escape HTML entities (XSS prevention)
  let html = escapeHtml(processed);

  // Step 3: Restore code blocks with styling
  html = html.replace(/%%CODEBLOCK_(\d+)%%/g, (_m, idx) => {
    const code = escapeHtml(codeBlocks[parseInt(idx)]);
    return `<pre class="bg-muted p-2 rounded text-sm overflow-x-auto my-2"><code>${code}</code></pre>`;
  });

  // Step 4: Restore tables with parsed HTML
  html = html.replace(/%%TABLE_(\d+)%%/g, (_m, idx) => {
    const tableText = tableBlocks[parseInt(idx)];
    return parseTable(escapeHtml(tableText));
  });

  // Step 5: Markdown inline transformations (order matters)

  // Inline code `code`
  html = html.replace(
    /`([^`]+)`/g,
    '<code class="bg-muted px-1 py-0.5 rounded text-sm font-mono">$1</code>'
  );

  // Headings ### h3, ## h2 (before bold, since ## can conflict)
  html = html.replace(/^### (.+)$/gm, '<h4 class="font-semibold text-sm mt-4 mb-2">$1</h4>');
  html = html.replace(/^## (.+)$/gm, '<h3 class="font-semibold text-base mt-5 mb-2">$1</h3>');

  // Bold **text**
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong class="font-semibold">$1</strong>');

  // Italic *text*
  html = html.replace(/\*([^*]+)\*/g, '<em class="italic">$1</em>');

  // Bullet lists - item (consecutive lines)
  html = html.replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>');
  html = html.replace(
    /(<li class="ml-4 list-disc">[\s\S]*?<\/li>)/g,
    '<ul class="my-1">$1</ul>'
  );
  // Clean double-wrapped <ul>
  html = html.replace(/<\/ul>\s*<ul class="my-1">/g, '');

  // Numbered lists 1. item
  html = html.replace(/^\d+\. (.+)$/gm, '<li class="ml-4 list-decimal">$1</li>');

  // Links [text](url) — only if not already escaped
  html = html.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-primary hover:underline">$1</a>'
  );

  // Line breaks: double newline = paragraph break (proper spacing)
  html = html.replace(/\n\n/g, '<div class="mb-3"></div>');

  return html;
}
