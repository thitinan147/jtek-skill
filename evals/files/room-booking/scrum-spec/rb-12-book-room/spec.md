<!-- scrum-spec -->
# rb-12-book-room

## Story

- **Ticket:** RB-12
- **Story:** As a staff member I want to book a free meeting room myself so that I do not wait for admin to book it
- **In scope:**
  - Pick the date, start time, end time and room, then press "Book"
  - Only admin can book the large meeting room
- **Out of scope:**
  - Cancelling a booking (RB-13)
  - Email notifications
- **Source:** PO note 2026-11-02 · `src/booking/BookingPage.tsx` · `src/rooms/rooms.ts`

## Rules

- **Permissions**
  - Only admin sees and books the large meeting room
- **Form**
  - Date, start time, end time and room are required
  - A booking lasts at most 4 hours (D1)

## Acceptance Criteria

**approve:** ✅ Alex · 2026-11-03 (incl. D1)

| # | Given | When | Then |
|---|---|---|---|
| AC1 | Staff picked a date, times and a free room | they look at the "Book" button | the button is enabled |
| AC2 | The form is complete | they press "Book" | the booking shows in "My bookings" |
| EC1 | The user is not admin | they open the room list | the large meeting room is not listed |
| EC2 | The room is booked in that slot | they press "Book" | they see "This room is already booked" |
| EC3 | Staff pick 09:00 to 14:00 | they press "Book" | they see that a booking can last at most 4 hours |

## Questions

| # | Question | Ask | Blocks | Answer |
|---|---|---|---|---|
| Q2 | Should the "Book" button show a spinner while saving? | UX | later | |

## Decisions

- **D1** A booking lasts at most 4 hours · Alex · 2026-11-03

## Test steps

- **Accounts:** Admin Alex (admin) · Staff Sam (staff, no access to the large room)
- **Data to prepare:** Room 1 booked 10:00–11:00 today
- **Do not report:** cancelling a booking (RB-13) · email notifications

### AC1 Book button enabled

1. Log in as Staff Sam
2. Open "Book a meeting room" and fill in every field

### AC2 Booking shows in My bookings

1. Log in as Staff Sam
2. Book Room 2 for 13:00–14:00 today

### EC1 Large room hidden from staff

1. Log in as Staff Sam
2. Open "Book a meeting room"

### EC3 Booking longer than 4 hours

1. Log in as Staff Sam
2. Book Room 2 from 09:00 to 14:00 today

### EC2 Room already booked

1. Log in as Staff Sam
2. Book Room 1 for 10:00–11:00 today

### Watch out

1. Room list — the same `listRooms` feeds other screens · check they still list rooms for admin
