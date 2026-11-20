# Knowledge folder

Every `.md` or `.txt` file in this folder (except this README) is added to Claude's instructions when it writes a rule.

Use it to teach Claude your environment, for example:

- `datasets.md`: your real dataset names and the fields each one has
- `naming.md`: your rule naming convention and severity scheme
- `exclusions.md`: known-good hosts, service accounts and paths to always exclude
- `xql-notes.md`: XQL patterns your team prefers

Keep the total under about 60 KB. Anything beyond that is cut off.
