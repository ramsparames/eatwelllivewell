NourisHer Phase 1.2 — Automatic Synamate Calendar Detection

You no longer need to configure:
- SYNAMATE_CLARITY_CALENDAR_ID
- SYNAMATE_COACHING_CALENDAR_ID

NourisHer automatically recognizes:
- Clarity Call with Sushma
- Coaching Call with Sushma

using the calendar_id + title/raw webhook payload already saved in
clarity_call_appointments.

Existing environment variables you keep:
- SYNAMATE_API_TOKEN
- SYNAMATE_LOCATION_ID
- SYNAMATE_SECRET_WEBHOOK

Optional booking-page URLs:
- SYNAMATE_CLARITY_CALL_URL
- SYNAMATE_COACHING_CALL_URL

Those URLs are only needed for the "Schedule..." buttons. They are not needed
for recognizing or syncing booked appointments.

Optional name overrides (only if you rename the calendars):
- SYNAMATE_CLARITY_CALENDAR_NAME
- SYNAMATE_COACHING_CALENDAR_NAME

Defaults:
SYNAMATE_CLARITY_CALENDAR_NAME="Clarity Call with Sushma"
SYNAMATE_COACHING_CALENDAR_NAME="Coaching Call with Sushma"

IMPORTANT FIRST-BOOKING BEHAVIOR
A newly created calendar cannot be recognized from webhook history until
Synamate has sent at least one appointment webhook from that calendar.

For the newly-created "Coaching Call with Sushma":
1. Make one test booking (test7 is ideal).
2. Let Synamate send the existing calendar webhook.
3. Refresh /dashboard/synamate-calendars.
4. It should show:
   Clarity Call -> Clarity Call with Sushma calendar_id
   Coaching Call -> Coaching Call with Sushma calendar_id
5. Open test7 again. Only the Coaching Call appointment will appear as the
   client's next coaching call.

The explicit *_CALENDAR_ID environment variables are still accepted as
emergency overrides, but should normally be left unset.
