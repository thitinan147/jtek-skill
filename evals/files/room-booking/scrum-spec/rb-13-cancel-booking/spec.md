<!-- scrum-spec -->
# rb-13-cancel-booking

## Story

- **Ticket:** RB-13
- **Story:** As a staff member I want to cancel my booking so that the room is free for others
- **In scope:**
  - Cancel a booking from "My bookings"
- **Out of scope:**
  - Editing a booking
- **Source:** PO note 2026-11-05 · `src/booking/api.ts` (no cancel API yet)

## Rules

- **Permissions**
  - Staff cancel only their own bookings

## Acceptance Criteria

**approve:** ❌ waiting for PO

| # | Given | When | Then |
|---|---|---|---|
| AC1 | Staff have a future booking | they press "Cancel" and confirm | the booking leaves "My bookings" |
| EC1 | The booking has already started | they look at it | there is no "Cancel" button |

## Questions

| # | Question | Ask | Blocks | Answer |
|---|---|---|---|---|
| Q1 | Can admin cancel anyone's booking? Proposal: yes | PO | AC | yes, admin can cancel any booking — Alex |
| Q2 | A cancel API does not exist. Proposal: `DELETE /bookings/:id`, 403 when not the owner | BE | dev | |
| Q3 | Should the cancel confirmation have custom text? | UX | later | |

## Decisions

- (none yet)
