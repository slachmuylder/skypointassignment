**To:** [CFO name]
**From:** [Your name], Data & Analytics Engineer
**Subject:** Re: August occupancy discrepancy (87.2% vs 89.4%)

Hi [CFO name],

Thanks for flagging this — a 2.2-point gap is worth running down properly
before either number gets used for a decision, so I'm not going to just
push the dashboard number to match the internal report without first
confirming which one is actually right. Two reports disagreeing usually
means they're measuring slightly different things, not that one of them is
simply broken.

**What I'm checking today, in order:**

1. **Definition of occupancy** — occupied units ÷ total units, or occupied
   beds ÷ licensed beds? A different IL/AL/MC unit mix between the two
   calculations alone can produce a gap this size.
2. **Timing** — is the internal report a point-in-time snapshot (e.g. last
   day of August), while the dashboard averages daily occupancy across the
   whole month? If occupancy was trending up through August, a month
   average will read lower than a month-end snapshot even if both are
   "correct."
3. **Denominator** — does one of the two exclude units offline for
   renovation or maintenance while the other counts them as available?
4. **Scope** — does "August occupancy" mean the same 14 communities in
   both reports, or does one include/exclude a community the other
   doesn't?
5. **Data freshness** — does the internal report include a late-arriving
   PCC or Yardi update that hadn't landed in our extract yet as of the
   dashboard's last refresh?

I'll have an answer on which of these explains the gap — and which number
is actually correct — by [tomorrow morning / specific commitment]. If the
dashboard is wrong, I'll fix the underlying calculation (not just the
displayed number) and add a validation check so this specific discrepancy
can't silently reappear in a future month. If the internal report turns
out to be the one that's off, I'll document exactly why so we have a clear,
reusable answer the next time this comes up.

I'll follow up by [time] either way.

Best,
[Your name]
