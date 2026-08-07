# NourisHer Product Architecture

## 1. Product Surfaces

NourisHer will support three interfaces.

### A. Coach Web
Primary user: Coach

Used for:
- Leads
- Clients
- Weekly coaching
- Calls
- Progress review
- Resources
- Administration

### B. Coach Mobile App
Primary user: Coach

Used for:
- Today's agenda
- Client lookup
- Quick client review
- Weekly check-in
- Calls
- Follow-ups
- Notifications

### C. Client Mobile App
Primary user: Coaching client

Used for:
- Today's actions
- Daily tracking
- Protein
- Water
- Steps
- Strength
- Stress
- Mood
- Progress
- Next call
- Coaching resources

---

## 2. Shared Backend

All interfaces use one backend.

FastAPI
↓
Service layer
↓
PostgreSQL

Examples:

dashboard.py / API routes
↓
ClientService
LeadService
TrackingService
↓
database.py
↓
PostgreSQL

## 3. Architecture Rule

Business rules belong in the service layer.

Bad:

Web template calculates:
- current week
- adherence
- weight change
- who is overdue

Good:

ClientService calculates them and returns structured data.

This allows both web and mobile to use the same logic.

## 4. API Direction

Current web routes can continue rendering HTML.

Mobile-ready JSON routes will gradually be added.

Examples:

GET /api/coach/today

GET /api/clients

GET /api/clients/{client_id}

GET /api/clients/{client_id}/checkins

POST /api/clients/{client_id}/checkins

GET /api/clients/{client_id}/tracking

POST /api/clients/{client_id}/tracking

GET /api/clients/{client_id}/actions

POST /api/clients/{client_id}/actions

## 5. Shared Data Model

Core entities:

- Lead
- Client
- Weekly Check-in
- Action Plan
- Daily Tracking
- Measurement
- Resource
- Coaching Call

The web dashboard and mobile apps must use the same records.
There must never be separate web-client and mobile-client databases.
