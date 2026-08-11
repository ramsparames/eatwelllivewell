NourisHer Phase 1 + Call Prep

What this adds
--------------
1. Existing Synamate Clarity Call calendar integration is used, not duplicated.
2. Lead detail: Schedule Clarity Call button + webhook-synced booked call.
3. Dashboard Today’s Calls: combines client coaching calls and webhook-synced Synamate calls.
4. Client workspace: Synamate next-call status + optional Schedule in Synamate button.
5. Client portal: upcoming coaching call card; reschedule link shown when present in Synamate webhook payload.
6. Weekly Check-in: automatic Call Prep summary with check-in consistency, action adherence, average steps, weight trend, measurement changes and attention flags.

Environment variables
---------------------
Required for lead scheduling button:
SYNAMATE_CLARITY_CALL_URL=https://<your Synamate Clarity Call booking page>

Optional for active-client coaching-call scheduling:
SYNAMATE_COACHING_CALL_URL=https://<your Synamate coaching calendar booking page>

The current codebase contains the Clarity Call webhook storage but does not contain the public booking URL, so this package deliberately does not guess it.

No webhook rewrite is required. The existing webhook continues writing to clarity_call_appointments; this phase reads that table and syncs the UI from it.

Files changed
-------------
app/database.py
app/dashboard.py
app/coach/clients.py
app/client/portal.py
app/services/client_portal_service.py
templates/dashboard_home.html
templates/coach/dashboard_home.html
templates/coach/lead.html
templates/coach/client_workspace.html
templates/client/home.html
