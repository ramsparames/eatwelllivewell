# NourisHer Coach OS Design System

## 1. Product Principles

NourisHer is a coaching operating system, not a generic CRM.

Each screen should answer one primary question:

- Today: What needs my attention?
- Clients: Who am I actively coaching?
- Leads: Who needs follow-up?
- Client Journey: How is this person doing?
- Insights: What patterns should I notice?

The interface should feel calm, premium, warm and easy to scan.

---

## 2. Navigation

Primary navigation:

- Today
- Clients
- Leads
- Library
- Insights
- Settings

Desktop:
- Narrow left sidebar
- Minimal top bar
- Main content gets maximum width

Mobile:
- Bottom navigation for core areas
- Secondary items inside More / Settings

---

## 3. Color Roles

Purple:
- Primary actions
- Active navigation
- Links
- Section accents

Green:
- Progress
- Health
- Completion
- Positive outcomes

Orange:
- Needs attention
- Caution
- Follow-up due

Red:
- Urgent
- Overdue
- Error

Neutral:
- Main text
- Secondary text
- Borders
- Backgrounds

Avoid decorative color unless it communicates meaning.

---

## 4. Typography

Use one consistent hierarchy.

Page title:
- 36px desktop
- 30px mobile
- Bold

Section heading:
- 26px desktop
- 22px mobile

Card heading:
- 18px

Body:
- 15–16px

Caption / label:
- 11–12px
- Uppercase only when useful

Avoid multiple competing heading sizes on the same page.

---

## 5. Spacing

Base spacing scale:

- 8px
- 16px
- 24px
- 32px
- 48px
- 64px

Use these consistently.

---

## 6. Core Components

### Metric Card
Used for:
- Active clients
- Calls today
- New leads
- Weekly adherence

### Person Card
Used for:
- Client
- Lead
- Upcoming call

Contains:
- Name
- Program / status
- One or two key metrics
- Next action

### Agenda Row
Used for:
- Calls today
- Calls this week
- Follow-ups

### Status Badge
Examples:
- Active
- New
- Follow-up due
- Completed
- Overdue

### Action Item
Used for:
- Protein
- Water
- Steps
- Strength
- Other weekly actions

### Journey Card
Used for one coaching week.

Contains:
- Week/date
- Weight
- Mood
- Stress
- Action plan
- Next call

---

## 7. Page Layouts

### Today

Primary question:
What needs my attention today?

Sections:
- Calls today
- Needs attention
- New leads
- Quick actions
- This week

Do not duplicate detailed data from Leads or Clients.

---

### Clients

Primary question:
Who am I actively coaching?

Order:
1. Search/filter
2. Client cards
3. Calls today / upcoming
4. Add client

---

### Leads

Primary question:
Who needs follow-up?

Keep current lead metrics and follow-up emphasis.

Use the same typography, spacing, sidebar and page width as Clients and Today.

---

### Client Journey

Primary question:
How is this client doing?

Top snapshot:
- Program
- Current week
- Starting weight
- Current weight
- Goal weight
- Next call
- Current actions

Below:
- Current week
- Previous coaching weeks
- Progress
- Measurements

Main page is primarily for review.

Editing happens through focused check-in/action forms or modal/drawer patterns.

---

## 8. Responsive Behaviour

Web desktop:
- Sidebar 180–200px
- Content gets remaining width
- Two-column layouts where useful

Tablet:
- Sidebar can collapse
- Cards reduce to 1–2 columns

Mobile:
- Bottom navigation
- Single-column layouts
- Large touch targets
- No hover-dependent interactions
- Important coaching actions reachable with one hand

---

## 9. Cross-Platform Rule

Components are defined by purpose, not by HTML.

For example:
- Person Card
- Metric Card
- Agenda Row
- Journey Card
- Status Badge

Web and mobile implement the same component concept using their own UI technology.

Business logic must not live only inside templates or browser JavaScript.
