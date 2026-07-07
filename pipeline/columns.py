"""Canonical column-name constants for the two identifiers used as
join/filter keys across almost every stage of the pipeline and API:
community_id and resident_id. Centralized so a rename only has to happen in
one place, instead of relying on a manual find-and-replace across every
DataFrame column access and dict-key construction that references them.

Deliberately narrow in scope: this does not attempt to cover every column
name in the dataset (most appear once or twice in one function, where a
plain literal is clearer), and it does not cover community_id/resident_id
references embedded in raw SQL text (api/queries.py) or JWT claim keys
(api/auth.py) -- those are conceptually different things that happen to
share the same string value, not the same maintenance risk this solves.
"""

COMMUNITY_ID = "community_id"
RESIDENT_ID = "resident_id"
