# Reading a PDF or image

- Images (PNG, JPG): open them with Read
- PDF: try Read first. Too large: `pdftotext -layout "<file.pdf>" "<temp folder>/input.txt"`. If `pdftotext` is missing, ask the user to install poppler (macOS `brew install poppler` · Debian/Ubuntu `apt install poppler-utils`) or to paste the text; do not install it yourself
- A board is often one huge page: crop only the part you need. Find coordinates with `pdftotext -bbox`, then `pdftoppm -q -r 36 -x <x> -y <y> -W <w> -H <h> -png "<file.pdf>" "<temp folder>/crop"`
- Several tickets on one board: use only the one the user named, else ask which
- Figma or Miro links cannot be opened: ask for a PDF or image export
- Long input: copy the exact text of the parts you use first, then summarise from that text only. Cite the source, e.g. "PDF p.2" or "frames C.1–C.4"

## Languages that lose marks in PDFs

Thai, Lao, Khmer and Devanagari text often loses vowel or tone marks when extracted, e.g. "ห้องประชุม" becomes "หองประชม".

- Restore a mark only when the word has one possible reading; render key parts (scope, names) as an image and look
- List every word you restored in chat as `Words I filled in: …` and ask about any proper name you are unsure of
- Never copy customer personal data, passwords or tokens from the input
