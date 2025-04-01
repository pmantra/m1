# Appointments

+**This file no longer maintained. It has been ported to [Notion](https://www.notion.so/mavenclinic/Booking-Flow-00c7c2d594024ed0be106a7b05b10580).**

## Design
### Booking
The booking flow endpoint `/v1/booking_flow` is a key part of the appointment process. This endpoint provides all the practitioner, vertical, and specialty information to an app or the web. That information is then cached and filtered on the client side. The initial load of data is slow, but allows the client side appointment selection process to be very responsive. Notably, the booking flow filters out the care advocate vertical, though care advocates do have practitioner profiles. Another thing to keep in mind about `/v1/booking_flow` is that it filters practitioners on `next_availability` and `show_when_unavailable`, which means that practitioners can briefly disappear from the list while the `update_practitioners_next_availability` job is running, and that unavailable practitioners display if they're supposed to be open to requests.

After a user has gone through the booking flow data, they select a specific practitioner. Clicking into that practitioner's profile will reveal their availabilities via the `/v1/products/<int:product_id>/availability` endpoint. Again, this endpoint provides a large amount of data to be handled on the client side. These are the potential appointments calculated from the practitioner's products and existing AVAILABLE status schedule events. When a user selects one of the events, they then move into the payment flow and after paying, the resulting booking posts to `v1/appointments`. The logic for calculating potential appointments is in `utils/booking.py`.

Note that users can only make appointments up to seven days out, because we have no charge-renewal code. This may change in the future.

Review:
* A Schedule Element is an abstract rule about the availability and duration of events.
* A Schedule Event is a specific start time and end time that may be available, unavailable, or contingent.
* A Schedule is the group of events and elements that belongs to a specific user.
* An Appointment is tied to a schedule event.
* Next Availability is stored on the Practitioner Profile and updated via the `update_practitioner_next_availability_job` cron job.
