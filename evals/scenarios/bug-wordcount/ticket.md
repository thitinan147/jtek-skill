# Word count is wrong for lines and repeated spaces
id: B-1
status: Todo
kind: bug

## Goal
`wordcount.py` reports too many or too few words when a file has newlines, tabs, or several spaces in a row. A user compared it with `wc -w` and the numbers differ.

## Done when
- a file containing `one  two\nthree\tfour\n` counts as 4 words
- an empty file counts as 0 words
- the count for a file with single spaces is the same as before

## Out of scope
- the output format
- reading from standard input
