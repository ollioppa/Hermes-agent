# New illustrative example: count lines without changing a file

**Created for this export.** The source facts, weak Before text and After text below are a newly constructed teaching example. They are not private documents, a historical application, a controlled comparison or evidence that another reader succeeded. The command was executed locally: three lines returned 3, an empty file returned 0, and a final newline did not add a line. This is a command check, not an independent reader study.

## Source facts and assignment

- Reader: someone comfortable opening a terminal, unfamiliar with Python line counting.
- Task: count all lines in a UTF-8 text file without changing it. Blank lines count. A final line without a newline counts too. This is not a count of words, records or nonempty lines.
- Environment: Python 3 available as `python3`; a terminal opened in the directory containing `sample.txt`.
- Fixture: `sample.txt` contains exactly `apple\n\npear`, where `\n` means a newline character. This is three lines, with no final newline.
- Implementation: `Path.read_text(encoding='utf-8').splitlines()` reads and splits text; `len(...)` counts the resulting lines. An empty file yields zero. The command loads the file in memory; this guide is not for very large files.
- Boundaries: no write operation in the counting command; missing file and invalid UTF-8 need explicit recovery. Do not silently ignore decoding errors or overwrite the input.
- Requested output: a compact English how-to. One action path is sufficient; no adoption claim or second presentation is needed.

These are the complete source facts for the exercise, not claims about a separate product. The preservation baseline is the table below.

## Before — deliberately weak draft

Use Python to inspect your content. Run the line counter on the input and check the count. If it fails, fix the file and try again. This makes processing easy.

## After — method applied

### Count every line in a small text file

This command counts lines, including blank ones, without changing your file. It also counts a final line without a trailing newline. It does not count words or nonempty records.

**Before starting:** use a small UTF-8 file named `sample.txt`, have Python 3 available as `python3`, and open a terminal in the folder containing the file. The command reads the whole file into memory, so choose another approach for very large files.

For the practice input, use a text editor to create `sample.txt` in a new practice folder. Enter `apple` on line one, leave line two blank, and enter `pear` on line three. A final newline is optional for this count. Save as UTF-8. Use a new file; do not replace existing work.

Run in that folder:

```sh
python3 -c "from pathlib import Path; print(len(Path('sample.txt').read_text(encoding='utf-8').splitlines()))"
```

For the practice input, expect `3`. The blank middle line is included. For your own file, the result depends on its contents; `3` is not a universal success value. The command contains no write operation.

If `python3` is not found, use a system with Python 3 installed before retrying. If you see `FileNotFoundError`, check the terminal's folder and exact filename. If you see `UnicodeDecodeError`, stop and verify the source encoding; work on a UTF-8 copy rather than discarding characters or overwriting the original.

You now have a line count with its meaning defined. Keep the input unchanged; a different count is a reason to inspect its lines, not to alter them until the expected number appears.

## Decision preservation and own quality review

The Before text omits essential facts; recovering them from the supplied factbase is not evidence that they were present in the draft. The actual editorial application here is source-first repair, not just polishing its sentences.

| Decision from the factbase | Disposition and After location | Own check / limit |
| --- | --- | --- |
| Count all lines, including blank and unterminated final line | Restored explicitly in opening and expected result | Fixture and empty-file command checks; no claim about all possible file formats. |
| Do not modify input | Preserved from source; opening, command and ending | Local execution compared input bytes before/after. |
| Python 3, UTF-8, correct folder/name | Restored before action | Tested in a fresh local directory; recipient installation not tested. |
| Small files only | Restored before action | Command reads entire text; no memory benchmark claimed. |
| Exact action and success sign | Replaced vague instruction with command and conditional `3` | Real local fixture result recorded separately. |
| Recover without corrupting source | Replaced vague “fix the file” with named error handling | Missing-file and decoding-error cases exercised locally. |
| Compact focused how-to | Single path retained; filler removed | Own editorial review, not a reader study. |

For an additional revision, ask to shorten the After while retaining these decisions. Check their meaning and position, not just whether “UTF-8” or “3” still appears somewhere. The generic method's Quickstart/Presentation distinction remains intact even though this narrowly scoped example legitimately needs one path.
