// POST /bookings. Responds 409 when the room is already booked in that slot.
export async function createBooking(body: { roomId: string; date: string; start: string; end: string }) {
  const res = await fetch("/bookings", { method: "POST", body: JSON.stringify(body) });
  if (res.status === 409) throw new Error("This room is already booked");
  return res.json();
}

// DELETE /bookings/:id does not exist yet.
