// Booking page: pick date, time and room, then press "Book".
import { createBooking } from "./api";
import { listRooms } from "../rooms/rooms";

export function BookingPage({ user }: { user: { role: "staff" | "admin" } }) {
  const rooms = listRooms(user);
  const canBook = (form: { date?: string; start?: string; end?: string; roomId?: string }) =>
    Boolean(form.date && form.start && form.end && form.roomId);
  return { rooms, canBook, submit: createBooking };
}
