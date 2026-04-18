from html.parser import HTMLParser


class SimpleTableParser(HTMLParser):
    """Extract tables from HTML as structured text."""

    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.current_row = []
        self.rows = []
        self.current_cell = ""

    def handle_starttag(self, tag, attrs):
        if tag == "table": self.in_table = True
        elif tag == "tr": self.in_row = True; self.current_row = []
        elif tag in ("td", "th"): self.in_cell = True; self.current_cell = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.in_cell = False
            self.current_row.append(self.current_cell.strip())
        elif tag == "tr":
            self.in_row = False
            if self.current_row:
                self.rows.append(self.current_row)
        elif tag == "table":
            self.in_table = False

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data


def html_table_to_text(html_content):
    """Convert HTML tables to readable text with labels."""
    parser = SimpleTableParser()
    parser.feed(html_content)
    if not parser.rows:
        return html_content
    headers = parser.rows[0]
    text_rows = []
    for row in parser.rows[1:]:
        pairs = [f"{headers[i]}: {row[i]}" for i in range(min(len(headers), len(row)))]
        text_rows.append(" | ".join(pairs))
    return "\n".join(text_rows)
