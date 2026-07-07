**To:** Karen Mills, Director of IT
**From:** [Your name], Data & Analytics Engineer
**Subject:** Access request — PointClickCare, Yardi, ADP, Google Business Profile, HubSpot

Hi Karen,

To get started on the reporting platform for the COO, I need read-only access
to five systems. Here's exactly what I'm asking for from each, and why:

1. **PointClickCare** — a read-only API user (or scheduled export credential)
   covering resident census, incidents, and care-level change history for
   all 14 communities. This is the clinical backbone for the occupancy,
   incident-rate, and care-quality reporting.

2. **Yardi Senior Living** — read-only API or export access to unit
   inventory and lease records for all communities. Drives the occupancy
   and revenue numbers.

3. **ADP** — read access to shift and labor-cost data (export or API) for
   all communities. Labor cost per resident-day is one of the four metrics
   the COO specifically asked for.

4. **Google Business Profile** — an API key or OAuth connection to
   whichever account manages Pinewood's 14 location listings. This is the
   only source we have for care-quality signal from residents' families
   directly (reviews/ratings), so it matters even though it's the smallest
   dataset.

5. **HubSpot** — a private-app access token with read-only scope on
   contacts/deals (leads, tours, deposits). Feeds the sales-funnel and
   move-in conversion reporting.

I don't need write access anywhere — every credential above should be
provisioned read-only.

**What happens next on my end:** once I have credentials for a system, I'll
add it to an ingestion pipeline that lands the data in a staging layer, then
builds the reporting models the dashboard reads from. I'll start with a
historical backfill and then move to a recurring incremental pull once
each connection is live, so there's no need to hold everything until all
five are ready — I can start as soon as the first one comes through.

Two logistics questions: is there a standard process Pinewood uses for
provisioning API credentials (a shared secrets vault, a ticket, etc.), and
is there a technical contact at each vendor I should loop in if I hit rate
limits or scope questions during setup?

Happy to jump on a call if that's faster than back-and-forth over email.

Thanks,
[Your name]
