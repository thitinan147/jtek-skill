export type Room = { id: string; name: string; large: boolean };

const ROOMS: Room[] = [
  { id: "r1", name: "Room 1", large: false },
  { id: "r2", name: "Room 2", large: false },
  { id: "big", name: "Large meeting room", large: true },
];

// Only admin sees the large meeting room.
export function listRooms(user: { role: "staff" | "admin" }): Room[] {
  return ROOMS.filter((r) => !r.large || user.role === "admin");
}
