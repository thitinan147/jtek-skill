# One parser for the config readers
id: R-1
kind: refactor
status: Todo

## Goal
`read_server` and `read_client` in `config.py` each parse `key = value` lines with their own copy of the same loop. Two copies drift apart. One helper should do the parsing.

## Done when
- `config.py` has one function that turns lines into key and value pairs, and both readers use it
- the existing tests pass unchanged
- `python3 config.py server examples/server.conf` and `python3 config.py client examples/client.conf` print the same output as before

## Out of scope
- the config file format
- what either reader returns for any input
