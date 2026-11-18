# Slug drops punctuation and repeated dashes
id: F-1
kind: feature
status: Todo

## Goal
`slugify` should produce clean slugs for titles that contain punctuation or several spaces in a row.

## Done when
- `python3 slug.py "Hello,   World!"` prints `hello-world`
- a title made only of punctuation gives an empty string, not dashes
- existing behaviour for plain titles is unchanged

## Out of scope
- non-ASCII letters
