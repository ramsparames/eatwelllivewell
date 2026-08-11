NourisHer Phase 1.1 — Synamate Calendar Source of Truth

Required Render environment variables:
SYNAMATE_CLARITY_CALL_URL=<public Clarity Call booking URL>
SYNAMATE_CLARITY_CALENDAR_ID=<Clarity calendar_id from webhook>
SYNAMATE_COACHING_CALL_URL=<public Coaching Call booking URL>
SYNAMATE_COACHING_CALENDAR_ID=<Coaching calendar_id from webhook>

After deploying, open:
  /dashboard/synamate-calendars

That page lists calendar IDs already received through the existing webhook.

Behavior:
- Leads use ONLY the Clarity Call calendar ID.
- Clients use ONLY the Coaching Call calendar ID.
- Old manual next_call_date/time values remain historical only.
- Weekly Check-in no longer asks for manual next-call date/time.
- Dashboard Today's Calls is Synamate-driven.
- Client workspace and portal show the same synced Coaching Call appointment.

Test7:
1. Configure both calendar IDs.
2. Open test7.
3. The 17 Aug 4 PM appointment should appear ONLY if its calendar_id is the Coaching Call ID.
4. If it belongs to the Clarity Call calendar, it will no longer be shown as a client call.
5. Book a Coaching Call from the Synamate button.
6. After webhook delivery, refresh workspace, portal and dashboard.
